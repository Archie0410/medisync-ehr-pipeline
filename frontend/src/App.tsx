import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchDocumentBlob } from "./api/client";
import { DocumentPreviewModal } from "./components/DocumentPreviewModal";
import { OrdersTable } from "./components/OrdersTable";
import { PatientList } from "./components/PatientList";
import { usePatientContext, usePatients } from "./hooks/usePatients";
import "./styles.css";

function App() {
  const [selectedMrn, setSelectedMrn] = useState<string | null>(null);
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
    <main className="page">
      <header className="header">
        <h1>MediSync Frontend</h1>
        <p className="sub">Scalable patient, order, and document workspace</p>
      </header>

      {!selectedMrn ? (
        <section>
          <h2>Patients</h2>
          {loading && <p className="hint">Loading patients...</p>}
          {error && <p className="error">{error}</p>}
          {!loading && !error && <PatientList patients={patients} onSelect={setSelectedMrn} />}
        </section>
      ) : (
        <section>
          <button className="mini-btn" onClick={() => setSelectedMrn(null)}>Back</button>
          <h2>{selectedPatientName || selectedMrn}</h2>
          {patientLoading && <p className="hint">Loading patient details...</p>}
          {patientError && <p className="error">{patientError}</p>}
          {!patientLoading && !patientError && (
            <>
              <div className="stats-row">
                <div className="stat-card">Episodes: {episodes.length}</div>
                <div className="stat-card">Orders: {orders.length}</div>
                <div className="stat-card">Documents: {documents.length}</div>
              </div>
              <h3>Orders and Documents</h3>
              <OrdersTable orders={orders} documents={documents} onViewDocument={openDocumentPreview} />
            </>
          )}
        </section>
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
  );
}

export default App;