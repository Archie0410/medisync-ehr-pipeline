import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { Document, Episode, Order, Patient, PatientOverview } from "../types/api";

export function usePatients() {
  const [patients, setPatients] = useState<PatientOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        setLoading(true);
        const data = await apiGet<PatientOverview[]>("/patients/overview?limit=500&offset=0");
        if (mounted) {
          setPatients(data);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load patients");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [tick]);

  const refetch = () => setTick((t) => t + 1);

  return { patients, loading, error, refetch };
}

export function usePatientContext(mrn?: string) {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const targetMrn = mrn;
    if (!targetMrn) {
      return;
    }
    const safeMrn: string = targetMrn;

    let mounted = true;

    async function load() {
      try {
        setLoading(true);
        const [patientData, episodesData, ordersData, documentsData] = await Promise.all([
          apiGet<Patient>(`/patients/${encodeURIComponent(safeMrn)}`),
          apiGet<Episode[]>(`/episodes?mrn=${encodeURIComponent(safeMrn)}`),
          apiGet<Order[]>(`/orders?mrn=${encodeURIComponent(safeMrn)}`),
          apiGet<Document[]>(`/documents/by-mrn?mrn=${encodeURIComponent(safeMrn)}`)
        ]);

        if (mounted) {
          setPatient(patientData);
          setEpisodes(episodesData);
          setOrders(ordersData);
          setDocuments(documentsData);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load patient details");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [mrn, tick]);

  const refetch = () => setTick((t) => t + 1);

  return { patient, episodes, orders, documents, loading, error, refetch };
}