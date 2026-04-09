"""Query the NPPES NPI Registry API and enrich patient physician data."""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.patient import Patient

logger = logging.getLogger("medisync.npi")

NPPES_API = "https://npiregistry.cms.hhs.gov/api/"


async def lookup_npi(npi: str) -> dict | None:
    """Query NPPES for a single NPI number. Returns parsed dict or None."""
    params = {"version": "2.1", "number": npi}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(NPPES_API, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("result_count", 0) == 0:
        return None

    return _parse_npi_result(data["results"][0])


def _parse_npi_result(result: dict) -> dict:
    basic = result.get("basic", {})
    addresses = result.get("addresses", [])
    taxonomies = result.get("taxonomies", [])

    location = next((a for a in addresses if a.get("address_purpose") == "LOCATION"), None)
    mailing = next((a for a in addresses if a.get("address_purpose") == "MAILING"), None)
    primary_taxonomy = next((t for t in taxonomies if t.get("primary")), taxonomies[0] if taxonomies else None)

    parsed: dict = {
        "npi": result.get("number"),
        "enumeration_type": result.get("enumeration_type"),
        "first_name": basic.get("first_name"),
        "last_name": basic.get("last_name"),
        "credential": basic.get("credential"),
        "name_prefix": basic.get("name_prefix"),
        "sex": basic.get("sex"),
        "status": basic.get("status"),
        "sole_proprietor": basic.get("sole_proprietor"),
        "enumeration_date": basic.get("enumeration_date"),
        "certification_date": basic.get("certification_date"),
        "last_updated": basic.get("last_updated"),
    }

    if basic.get("organization_name"):
        parsed["organization_name"] = basic["organization_name"]

    if primary_taxonomy:
        parsed["specialty"] = primary_taxonomy.get("desc")
        parsed["taxonomy_code"] = primary_taxonomy.get("code")
        parsed["taxonomy_license"] = primary_taxonomy.get("license")
        parsed["taxonomy_state"] = primary_taxonomy.get("state")

    if location:
        parsed["location_address"] = _format_address(location)
        parsed["location_phone"] = location.get("telephone_number")
        parsed["location_fax"] = location.get("fax_number")

    if mailing:
        parsed["mailing_address"] = _format_address(mailing)
        parsed["mailing_phone"] = mailing.get("telephone_number")

    if len(taxonomies) > 1:
        parsed["all_taxonomies"] = [
            {"code": t.get("code"), "desc": t.get("desc"), "primary": t.get("primary", False)}
            for t in taxonomies
        ]

    return parsed


async def sync_all_patient_npis(db: AsyncSession) -> dict:
    """Collect unique NPIs across ALL patients, look each up once, update every patient."""
    result = await db.execute(select(Patient))
    patients = list(result.scalars().all())

    npi_fields = ["attending_npi", "referring_npi", "certifying_npi"]

    npi_to_patients: dict[str, list[Patient]] = {}
    for patient in patients:
        profile = patient.profile_data or {}
        for field in npi_fields:
            npi_val = profile.get(field)
            if npi_val:
                npi_to_patients.setdefault(str(npi_val), []).append(patient)

    if not npi_to_patients:
        return {"synced": 0, "patients_updated": 0, "errors": []}

    npi_data: dict[str, dict] = {}
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=15) as client:
        for npi_number in npi_to_patients:
            try:
                info = await _lookup_npi_with_client(client, npi_number)
                if info:
                    npi_data[npi_number] = info
                else:
                    errors.append(f"NPI {npi_number}: not found in NPPES registry")
            except Exception as e:
                logger.warning("NPPES lookup failed for NPI %s: %s", npi_number, e)
                errors.append(f"NPI {npi_number}: {e}")

    patients_updated = set()
    for npi_number, info in npi_data.items():
        for patient in npi_to_patients.get(npi_number, []):
            profile = dict(patient.profile_data or {})
            existing_npi = dict(profile.get("npi_data", {}))
            existing_npi[npi_number] = info
            profile["npi_data"] = existing_npi
            patient.profile_data = profile
            flag_modified(patient, "profile_data")
            patients_updated.add(patient.id)

    if patients_updated:
        await db.flush()

    return {
        "synced": len(npi_data),
        "patients_updated": len(patients_updated),
        "errors": errors,
    }


async def _lookup_npi_with_client(client: httpx.AsyncClient, npi: str) -> dict | None:
    """Query NPPES using a shared client instance."""
    params = {"version": "2.1", "number": npi}
    resp = await client.get(NPPES_API, params=params)
    resp.raise_for_status()
    data = resp.json()

    if data.get("result_count", 0) == 0:
        return None

    return _parse_npi_result(data["results"][0])


def _format_address(addr: dict) -> str:
    parts = [addr.get("address_1", "")]
    if addr.get("address_2"):
        parts.append(addr["address_2"])
    city_state = f"{addr.get('city', '')}, {addr.get('state', '')} {addr.get('postal_code', '')}"
    parts.append(city_state)
    return ", ".join(p for p in parts if p.strip())
