import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchDocumentBlob } from "./api/client";
import { ClinicalSummary } from "./components/ClinicalSummary";
import { DocumentPreviewModal } from "./components/DocumentPreviewModal";
import { OrdersTable } from "./components/OrdersTable";
import { PatientList } from "./components/PatientList";
import { usePatientContext, usePatients } from "./hooks/usePatients";
import "./styles.css";

function formatDate(value?: string | null) {
  if (!value) {
    return "--";
  }

  const date = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  });
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return (
    date.toLocaleDateString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
    }) +
    " " +
    date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    })
  );
}

function displayValue(value?: string | number | null) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  return String(value);
}

function App() {
  const [selectedMrn, setSelectedMrn] = useState<string | null>(null);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<number | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTitle, setPreviewTitle] = useState("Document Preview");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const { patients, loading, error } = usePatients();
  const { patient, episodes, orders, documents, loading: patientLoading, error: patientError } = usePatientContext(selectedMrn ?? undefined);

  const selectedPatientName = useMemo(() => {
    if (!patient) return "";
    return `${patient.last_name}, ${patient.first_name}`;
  }, [patient]);

  const sortedEpisodes = useMemo(() => {
    return [...episodes].sort((a, b) => {
      const left = a.start_date ?? "";
      const right = b.start_date ?? "";
      return right.localeCompare(left);
    });
  }, [episodes]);

  const selectedEpisode = useMemo(() => {
    if (selectedEpisodeId === null) {
      return null;
    }

    return episodes.find((episode) => episode.id === selectedEpisodeId) ?? null;
  }, [episodes, selectedEpisodeId]);

  const visibleOrders = useMemo(() => {
    if (selectedEpisodeId === null) {
      return orders;
    }

    return orders.filter((order) => order.episode_id === selectedEpisodeId);
  }, [orders, selectedEpisodeId]);

  const visibleDocuments = useMemo(() => {
    const orderIds = new Set(visibleOrders.map((order) => order.order_id));
    return documents.filter((document) => orderIds.has(document.order_id));
  }, [documents, visibleOrders]);

  const patientInfoSections = useMemo(() => {
    if (!patient) {
      return [];
    }

    const profile = patient.profile_data ?? {};

    return [
      {
        title: "Demographics",
        fields: [
          ["MRN", patient.mrn],
          ["DOB", formatDate(patient.dob)],
          ["Phone", patient.phone],
          ["Sex", profile.sex],
          ["Race", profile.race],
          ["Ethnicity", profile.ethnicity],
          ["Primary Language", profile.primary_language],
          ["Email", profile.email],
        ],
      },
      {
        title: "Address",
        fields: [
          ["Primary Address", profile.primary_address],
          ["Mailing Address", profile.mailing_address],
          ["Service Location", profile.service_location],
          ["Emergency Contact", profile.emergency_contact_name],
          ["Emergency Phone", profile.emergency_contact_phone],
        ],
      },
      {
        title: "Clinical",
        fields: [
          ["Primary Diagnosis", profile.primary_diagnosis],
          ["Additional Diagnoses", profile.additional_diagnoses],
          ["Services Required", profile.services_required],
          ["Allergies", profile.allergies],
          ["Case Manager", profile.case_manager],
          ["Primary Clinician", profile.primary_clinician],
        ],
      },
      {
        title: "Coverage & Timeline",
        fields: [
          ["Primary Insurance", profile.primary_insurance],
          ["Secondary Insurance", profile.secondary_insurance],
          ["MBI Number", profile.mbi_number],
          ["Referral Date", formatDate(displayValue(profile.referral_date))],
          ["Created", formatDateTime(patient.created_at)],
          ["Updated", formatDateTime(patient.updated_at)],
        ],
      },
    ];
  }, [patient]);

  const closePreview = useCallback(() => {
    setPreviewOpen(false);
    setPreviewError(null);
    setPreviewLoading(false);
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    setSelectedEpisodeId(null);
  }, [selectedMrn]);

  async function openDocumentPreview(documentId: number, fileName?: string | null) {
    try {
      setPreviewOpen(true);
      setPreviewLoading(true);
      setPreviewError(null);
      setPreviewTitle(fileName ? `Preview: ${fileName}` : `Preview: Document ${documentId}`);

      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }

      const blob = await fetchDocumentBlob(documentId);
      const fileUrl = URL.createObjectURL(blob);
      setPreviewUrl(fileUrl);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Could not open document");
      setPreviewUrl(null);
    } finally {
      setPreviewLoading(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <div>
          <h1>MediSync Dashboard</h1>
          <p className="topbar-subtitle">Healthcare Data Pipeline</p>
        </div>
      </header>

      <main className="page">
        <section className="stats-bar">
          <div className="stat-card">
            <div className="stat-num">{patients.length}</div>
            <div className="stat-label">Patients</div>
          </div>
          <div className="stat-card">
            <div className="stat-num">{selectedMrn ? episodes.length : "--"}</div>
            <div className="stat-label">Episodes</div>
          </div>
          <div className="stat-card">
            <div className="stat-num">{selectedMrn ? orders.length : "--"}</div>
            <div className="stat-label">Orders</div>
          </div>
          <div className="stat-card">
            <div className="stat-num">{selectedMrn ? documents.length : "--"}</div>
            <div className="stat-label">Documents</div>
          </div>
        </section>

        {!selectedMrn ? (
          <section className="panel">
            <div className="section-title">
              <span className="section-icon">&#128100;</span>
              <span>Patients</span>
              <span className="section-count">{patients.length}</span>
            </div>
            {loading && <p className="hint">Loading patients...</p>}
            {error && <p className="error">{error}</p>}
            {!loading && !error && <PatientList patients={patients} onSelect={setSelectedMrn} />}
          </section>
        ) : (
          <>
            <div className="breadcrumb">
              <button className="breadcrumb-link" onClick={() => setSelectedMrn(null)}>
                Home Health
              </button>
              <span className="breadcrumb-sep">&gt;</span>
              <span className="breadcrumb-current">{selectedPatientName || selectedMrn}</span>
            </div>

            <section className="panel patient-panel">
              <button className="back-btn" onClick={() => setSelectedMrn(null)}>
                &larr; Back to patients
              </button>
              <h2>{selectedPatientName || selectedMrn}</h2>
              <p className="sub">Patient workspace and linked document preview</p>

              {patientLoading && <p className="hint">Loading patient details...</p>}
              {patientError && <p className="error">{patientError}</p>}

              {!patientLoading && !patientError && (
                <>
                  <div className="section-title compact">
                    <span className="section-icon">&#128197;</span>
                    <span>Episodes</span>
                    <span className="section-count">{episodes.length}</span>
                  </div>

                  {episodes.length === 0 ? (
                    <p className="hint">No episodes found for this patient.</p>
                  ) : (
                    <>
                      <div className="episode-grid">
                        {sortedEpisodes.map((episode) => (
                          <button
                            key={episode.id}
                            className={`episode-card${selectedEpisodeId === episode.id ? " active" : ""}`}
                            onClick={() => setSelectedEpisodeId(episode.id)}
                          >
                            <div className="episode-card-header">
                              <div className="episode-card-title">
                                {formatDate(episode.start_date)} - {formatDate(episode.end_date)}
                              </div>
                              <span className="badge-pill">
                                {displayValue(episode.status)}
                              </span>
                            </div>
                            <div className="episode-card-subtitle">
                              SOC: {formatDate(episode.soc_date)}
                            </div>
                            <div className="episode-card-meta">
                              <span>Episode #{episode.id}</span>
                              <span>Admission: {displayValue(episode.admission_id)}</span>
                            </div>
                          </button>
                        ))}
                      </div>

                      {selectedEpisode && (
                        <div className="episode-filter-bar">
                          <div className="summary-chip">
                            Showing orders for Episode #{selectedEpisode.id}
                          </div>
                          <button className="mini-btn" onClick={() => setSelectedEpisodeId(null)}>
                            Show all orders
                          </button>
                        </div>
                      )}
                    </>
                  )}

                  <div className="section-title compact">
                    <span className="section-icon">&#128100;</span>
                    <span>Patient Information</span>
                  </div>
                  <div className="patient-info-grid">
                    {patientInfoSections.map((section) => (
                      <div key={section.title} className="info-card">
                        <h3>{section.title}</h3>
                        <div className="info-grid">
                          {section.fields.map(([label, value]) => (
                            <div key={label} className="info-item">
                              <dt>{label}</dt>
                              <dd>{displayValue(value)}</dd>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="stats-row">
                    <div className="summary-chip">Episodes: {episodes.length}</div>
                    <div className="summary-chip">Orders: {visibleOrders.length}</div>
                    <div className="summary-chip">Documents: {visibleDocuments.length}</div>
                  </div>

                  <div className="section-title compact">
                    <span className="section-icon">&#128196;</span>
                    <span>{selectedEpisode ? `Episode #${selectedEpisode.id} Orders` : "Orders and Documents"}</span>
                  </div>
                  <OrdersTable orders={visibleOrders} documents={visibleDocuments} onViewDocument={openDocumentPreview} />

                  <ClinicalSummary mrn={selectedMrn} />
                </>
              )}
            </section>
          </>
        )}

        <DocumentPreviewModal
          isOpen={previewOpen}
          title={previewTitle}
          fileUrl={previewUrl}
          loading={previewLoading}
          error={previewError}
          onClose={closePreview}
        />
      </main>
    </>
  );
}

export default App;