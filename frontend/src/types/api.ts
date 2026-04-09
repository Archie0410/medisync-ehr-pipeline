export type PatientOverview = {
  mrn: string;
  first_name: string;
  last_name: string;
  dob?: string | null;
  phone?: string | null;
  episode_count?: number;
  order_count?: number;
  document_count?: number;
};

export type Patient = {
  id: number;
  mrn: string;
  first_name: string;
  last_name: string;
  dob?: string | null;
  phone?: string | null;
  profile_data?: Record<string, string | number | null>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Episode = {
  id: number;
  patient_id: number;
  admission_id?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  soc_date?: string | null;
  status?: string | null;
};

export type Document = {
  id: number;
  order_id: string;
  pdf_order_id?: string | null;
  filename?: string | null;
  doc_type?: string | null;
  status?: string | null;
  order_date?: string | null;
  created_at?: string | null;
};

export type Order = {
  id: number;
  order_id: string;
  episode_id?: number | null;
  doc_type?: string | null;
  order_date?: string | null;
  status?: string | null;
  created_at?: string | null;
};

export type ExtractionTriggerResponse = {
  extraction_id: number;
  status: string;
  message: string;
};

export type TimelineEntry = {
  date?: string | null;
  document_type?: string | null;
  clinician?: string | null;
  key_findings?: string[];
  vitals?: Record<string, string | null>;
  medications_mentioned?: string[];
  interventions?: string[];
  goals_or_plan?: string[];
  status_or_outcome?: string | null;
};

export type ExtractionData = {
  patient_summary?: {
    dob?: string | null;
    primary_diagnosis?: string | null;
    additional_diagnoses?: string[];
  };
  timeline?: TimelineEntry[];
  medications_across_visits?: string[];
  allergies?: string | null;
  overall_clinical_summary?: string | null;
  flags_or_concerns?: string[];
  message?: string;
};

export type Extraction = {
  id: number;
  patient_id: number;
  status: string;
  provider?: string | null;
  model_name?: string | null;
  documents_processed: number;
  structured_data?: ExtractionData | null;
  markdown?: string | null;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
};