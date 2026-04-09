import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { Extraction, ExtractionData, ExtractionTriggerResponse, TimelineEntry } from "../types/api";

type Props = {
  mrn: string;
};

function formatDate(value?: string | null) {
  if (!value) return "--";
  const d = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-US", { month: "2-digit", day: "2-digit", year: "numeric" });
}

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return (
    d.toLocaleDateString("en-US", { month: "2-digit", day: "2-digit", year: "numeric" }) +
    " " +
    d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
  );
}

function VitalsRow({ vitals }: { vitals?: Record<string, string | null> }) {
  if (!vitals) return null;
  const entries = Object.entries(vitals).filter(([, v]) => v);
  if (entries.length === 0) return null;
  return (
    <div className="cs-vitals">
      {entries.map(([k, v]) => (
        <span key={k} className="cs-vital-chip">
          <strong>{k.toUpperCase()}:</strong> {v}
        </span>
      ))}
    </div>
  );
}

function TimelineCard({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="cs-timeline-card">
      <div className="cs-timeline-header">
        <span className="cs-timeline-date">{formatDate(entry.date)}</span>
        <span className="cs-timeline-type">{entry.document_type ?? "Visit"}</span>
      </div>
      {entry.clinician && <div className="cs-timeline-clinician">Clinician: {entry.clinician}</div>}
      <VitalsRow vitals={entry.vitals} />
      {entry.key_findings && entry.key_findings.length > 0 && (
        <div className="cs-list-section">
          <strong>Key Findings</strong>
          <ul>{entry.key_findings.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      )}
      {entry.medications_mentioned && entry.medications_mentioned.length > 0 && (
        <div className="cs-pill-row">
          <strong>Medications:</strong>
          {entry.medications_mentioned.map((m, i) => <span key={i} className="cs-pill">{m}</span>)}
        </div>
      )}
      {entry.interventions && entry.interventions.length > 0 && (
        <div className="cs-list-section">
          <strong>Interventions</strong>
          <ul>{entry.interventions.map((item, i) => <li key={i}>{item}</li>)}</ul>
        </div>
      )}
      {entry.goals_or_plan && entry.goals_or_plan.length > 0 && (
        <div className="cs-list-section">
          <strong>Goals / Plan</strong>
          <ul>{entry.goals_or_plan.map((g, i) => <li key={i}>{g}</li>)}</ul>
        </div>
      )}
      {entry.status_or_outcome && (
        <div className="cs-status">Status: {entry.status_or_outcome}</div>
      )}
    </div>
  );
}

function SummaryContent({ data }: { data: ExtractionData }) {
  if (data.message) {
    return <p className="hint">{data.message}</p>;
  }

  const summary = data.patient_summary;
  const timeline = data.timeline ?? [];
  const meds = data.medications_across_visits ?? [];
  const flags = data.flags_or_concerns ?? [];

  return (
    <div className="cs-content">
      {data.overall_clinical_summary && (
        <div className="cs-overall">
          <h4>Overall Clinical Summary</h4>
          <p>{data.overall_clinical_summary}</p>
        </div>
      )}

      {summary && (
        <div className="cs-diagnosis-bar">
          <div className="cs-diag-item">
            <dt>Primary Diagnosis</dt>
            <dd>{summary.primary_diagnosis ?? "--"}</dd>
          </div>
          {summary.additional_diagnoses && summary.additional_diagnoses.length > 0 && (
            <div className="cs-diag-item">
              <dt>Additional Diagnoses</dt>
              <dd>{summary.additional_diagnoses.join(", ")}</dd>
            </div>
          )}
          {data.allergies && (
            <div className="cs-diag-item">
              <dt>Allergies</dt>
              <dd>{data.allergies}</dd>
            </div>
          )}
        </div>
      )}

      {flags.length > 0 && (
        <div className="cs-flags">
          <h4>&#9888; Flags &amp; Concerns</h4>
          <ul>{flags.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      )}

      {timeline.length > 0 && (
        <>
          <h4 className="cs-section-title">Visit Timeline ({timeline.length})</h4>
          <div className="cs-timeline-grid">
            {timeline.map((entry, i) => <TimelineCard key={i} entry={entry} />)}
          </div>
        </>
      )}

      {meds.length > 0 && (
        <div className="cs-meds-section">
          <h4>All Medications Across Visits</h4>
          <div className="cs-pill-row">
            {meds.map((m, i) => <span key={i} className="cs-pill">{m}</span>)}
          </div>
        </div>
      )}
    </div>
  );
}

export function ClinicalSummary({ mrn }: Props) {
  const [extractions, setExtractions] = useState<Extraction[]>([]);
  const [selected, setSelected] = useState<Extraction | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadExtractions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiGet<Extraction[]>(`/extractions/${encodeURIComponent(mrn)}`);
      setExtractions(data);
      if (data.length > 0) {
        setSelected(data[0]);
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes("404")) {
        setExtractions([]);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load extractions");
      }
    } finally {
      setLoading(false);
    }
  }, [mrn]);

  useEffect(() => {
    loadExtractions();
  }, [loadExtractions]);

  async function handleGenerate() {
    try {
      setGenerating(true);
      setError(null);
      const result = await apiPost<ExtractionTriggerResponse>(
        `/extractions/${encodeURIComponent(mrn)}`
      );
      if (result.status === "failed") {
        setError(result.message);
      } else {
        await loadExtractions();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate summary");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="cs-panel">
      <div className="cs-header">
        <div>
          <h3>&#129658; Clinical Summary</h3>
          <span className="cs-subtitle">LLM-powered analysis of patient documents</span>
        </div>
        <div className="cs-actions">
          {extractions.length > 1 && (
            <select
              className="cs-select"
              value={selected?.id ?? ""}
              onChange={(e) => {
                const ext = extractions.find((x) => x.id === Number(e.target.value));
                setSelected(ext ?? null);
              }}
            >
              {extractions.map((ext) => (
                <option key={ext.id} value={ext.id}>
                  {formatDateTime(ext.created_at)} — {ext.documents_processed} docs
                </option>
              ))}
            </select>
          )}
          <button
            className="cs-generate-btn"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating..." : extractions.length > 0 ? "Regenerate" : "Generate Summary"}
          </button>
        </div>
      </div>

      {loading && <p className="hint">Loading clinical summaries...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && selected && (
        <div className="cs-result">
          <div className="cs-meta-row">
            <span className="summary-chip">Status: {selected.status}</span>
            <span className="summary-chip">{selected.documents_processed} docs processed</span>
            {selected.provider && (
              <span className="summary-chip">{selected.provider} / {selected.model_name}</span>
            )}
            <span className="summary-chip">Generated: {formatDateTime(selected.completed_at)}</span>
          </div>

          {selected.status === "completed" && selected.structured_data && (
            <SummaryContent data={selected.structured_data} />
          )}

          {selected.status === "failed" && (
            <p className="error">Extraction failed: {selected.error_message}</p>
          )}

          {selected.status === "processing" && (
            <p className="hint">Extraction is still processing...</p>
          )}
        </div>
      )}

      {!loading && !error && extractions.length === 0 && (
        <p className="hint">
          No clinical summary yet. Click <strong>Generate Summary</strong> to analyze this patient's documents using AI.
        </p>
      )}
    </div>
  );
}
