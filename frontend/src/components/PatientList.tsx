import type { PatientOverview } from "../types/api";

type Props = {
  patients: PatientOverview[];
  onSelect: (mrn: string) => void;
};

export function PatientList({ patients, onSelect }: Props) {
  if (patients.length === 0) {
    return <p className="hint">No patients found yet.</p>;
  }

  return (
    <div className="card-grid">
      {patients.map((patient) => (
        <button key={patient.mrn} className="card" onClick={() => onSelect(patient.mrn)}>
          <div className="card-title">{patient.last_name}, {patient.first_name}</div>
          <div className="card-sub">MRN: {patient.mrn}</div>
          <div className="card-meta">
            <span>{patient.episode_count ?? 0} episodes</span>
            <span>{patient.order_count ?? 0} orders</span>
            <span>{patient.document_count ?? 0} docs</span>
          </div>
        </button>
      ))}
    </div>
  );
}