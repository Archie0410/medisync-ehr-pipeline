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
};

export type Episode = {
  id: number;
  patient_id: number;
  start_date?: string | null;
  end_date?: string | null;
  soc_date?: string | null;
  status?: string | null;
};

export type Document = {
  id: number;
  order_id: string;
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