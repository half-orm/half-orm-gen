export interface FieldSchema {
  name: string;
  sql_type: string;
  json_type: string;
  is_pk: boolean;
  not_null: boolean;
  has_default: boolean;
}

export interface FkDep {
  local_fields: string[];
  remote_schema: string;
  remote_table: string;
  remote_fields: string[];
}

export interface ReverseFk extends FkDep {
  is_singleton: boolean;
}

export interface ResourceSchema {
  schema: string;
  table: string;
  kind: string;
  pk_fields: string[];
  fields: FieldSchema[];
  fk_deps: FkDep[];
  reverse_fks: ReverseFk[];
  label_fields?: string[];
}

export type HoMeta = Record<string, ResourceSchema>;

export type Verb = 'GET' | 'POST' | 'PUT' | 'DELETE';
export type VerbAccess = {
  in?:           string[] | null;
  out?:          string[] | null;
  inherited_in?:  string[];
  inherited_out?: string[];
};
export type PermMatrix = Record<string, Partial<Record<Verb, VerbAccess>>>;
