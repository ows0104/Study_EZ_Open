import "../../../bridge/bank-file.js";

export type ResponseFileMetadata = { filename: string; sha256: string; byteLength: number };
export type BankFileResult = { raw: string; info: { prompt_version: string; question_count: number };
  responseFile: ResponseFileMetadata };
export type BankFileTarget = { subject: string; runId: string; promptVersion?: string };
const contract = (globalThis as unknown as { StudyEZBankFile: {
  readFile(file: File, target: BankFileTarget): Promise<BankFileResult>;
  metadata(raw: string): { generation_id?: string; prompt_version: string };
  inspect(raw: string, target: BankFileTarget, filename: string): unknown;
} }).StudyEZBankFile;

export function bankFileMetadata(raw: string) { return contract.metadata(raw); }
export function validBankFile(raw: string, target: BankFileTarget, filename: string) {
  try { contract.inspect(raw, target, filename); return true; } catch { return false; }
}

export function readBankFile(file: File, target: BankFileTarget) {
  return contract.readFile(file, target);
}
