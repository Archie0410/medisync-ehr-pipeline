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

export type ProfileData = {
  // Demographics
  alternate_phone?: string | null;
  ssn?: string | null;
  sex?: string | null;
  race?: string | null;
  ethnicity?: string | null;
  marital_status?: string | null;
  primary_language?: string | null;
  interpreter?: string | null;
  service_location?: string | null;
  auxiliary_aids?: string | null;
  // Address
  primary_address?: string | null;
  mailing_address?: string | null;
  email?: string | null;
  // Payer
  primary_insurance?: string | null;
  medicare_part_a_effective?: string | null;
  medicare_part_b_effective?: string | null;
  mbi_number?: string | null;
  secondary_insurance?: string | null;
  advanced_directive_comments?: string | null;
  // Pharmacy / Allergies / Directives
  pharmacy_name?: string | null;
  pharmacy_address?: string | null;
  pharmacy_phone?: string | null;
  allergies?: string | null;
  advanced_directives_type?: string | null;
  // Clinical
  case_manager?: string | null;
  clinical_manager?: string | null;
  primary_clinician?: string | null;
  services_required?: string | null;
  primary_diagnosis?: string | null;
  additional_diagnoses?: string | null;
  // Physicians
  attending_physician?: string | null;
  attending_npi?: string | null;
  attending_address?: string | null;
  attending_phone?: string | null;
  attending_fax?: string | null;
  careplan_oversight?: boolean | null;
  referring_physician?: string | null;
  referring_npi?: string | null;
  certifying_physician?: string | null;
  certifying_npi?: string | null;
  // Emergency contacts
  emergency_contact_name?: string | null;
  emergency_contact_relationship?: string | null;
  emergency_contact_phone?: string | null;
  legal_representative?: string | null;
  secondary_emergency_contact?: string | null;
  tertiary_emergency_contact?: string | null;
  cahps_contact?: string | null;
  // Referral
  referral_date?: string | null;
  admission_source?: string | null;
  name_of_referral_source?: string | null;
  community_liaison?: string | null;
  internal_referral_source?: string | null;
  facility_referral_source?: string | null;
  face_to_face_date?: string | null;
  priority_visit_type?: string | null;
  emergency_triage_level?: number | null;
  emergency_triage_description?: string | null;
  // Emergency Preparedness
  emergency_preparedness?: string | null;
  equipment_needs?: string | null;
  // Prior Episodes
  existing_prior_episodes?: string | null;
  // NPI enriched data (from NPPES registry sync)
  npi_data?: Record<string, NpiRecord>;
  // Admission Periods
  admission_periods?: Array<{
    admission_date?: string | null;
    discharge_date?: string | null;
    is_current?: boolean;
    associated_episodes?: boolean;
  }>;
};

export type NpiRecord = {
  npi?: string;
  enumeration_type?: string;
  first_name?: string;
  last_name?: string;
  credential?: string;
  name_prefix?: string;
  sex?: string;
  status?: string;
  sole_proprietor?: string;
  enumeration_date?: string;
  certification_date?: string;
  last_updated?: string;
  organization_name?: string;
  specialty?: string;
  taxonomy_code?: string;
  taxonomy_license?: string;
  taxonomy_state?: string;
  location_address?: string;
  location_phone?: string;
  location_fax?: string;
  mailing_address?: string;
  mailing_phone?: string;
  all_taxonomies?: Array<{ code?: string; desc?: string; primary?: boolean }>;
};

export type NpiSyncResult = {
  synced: number;
  patients_updated: number;
  errors: string[];
};

export type Patient = {
  id: number;
  mrn: string;
  first_name: string;
  last_name: string;
  dob?: string | null;
  phone?: string | null;
  profile_data?: ProfileData | null;
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