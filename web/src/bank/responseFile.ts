import "../../../bridge/bank-file.js";

export type ResponseFileMetadata = { filename: string; sha256: string; byteLength: number };
export type BankFileResult = { raw: string; info: { prompt_version: string; question_count: number };
  responseFile: ResponseFileMetadata };
export type BankFileTarget = { subject: string; runId: string; promptVersion?: string };
const contract = (globalThis as unknown as { StudyEZBankFile: {
  readFile(file: File, target: BankFileTarget): Promise<BankFileResult>;
} }).StudyEZBankFile;

export function readBankFile(file: File, target: BankFileTarget) {
  return contract.readFile(file, target);
}
