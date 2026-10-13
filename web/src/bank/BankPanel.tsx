import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import {
  absoluteUrl,
  bumpPreviewVersion,
  extensionCompatible,
  extensionInputMinimum,
  requestPreview,
} from "../bridge/previewBridge";
import { ExtensionSetup } from "../bridge/ExtensionSetup";
import { ActionCard, PanelGroup, PanelTool } from "../calendar/panelShared";
import { jobMoving, progressLine, runnerAlive } from "../jobProgress";
import { Link } from "react-router-dom";
import { bankHref } from "../links";
import type { BankSummary } from "../types/bank";
import type { LectureDetail, LectureRef } from "../types/lectures";
import type { PrequizJob, RunnerBeat } from "../types/jobs";
import { useMe } from "../useMe";
import { renderBankPrompt } from "./prompt";
import { BankCoverage } from "./BankCoverage";

/** ChatGPT 문제은행 링크와 별도 CLI 세션의 Main-Quiz 생성·학습. */
export function BankPanel({ lecture, detail }: { lecture: Pick<LectureRef, "subject" | "runId">; detail: LectureDetail }) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const bank = detail.bank;
  if (!isAdmin) {
    return (
      <>
      {bank?.shareUrl ? <PanelGroup tone="bank" title="문제은행 링크">
        <ActionCard shape="is-key" hit={
          <a className="panel-action-hit" href={bank.shareUrl} target="_blank" rel="noreferrer">
            <strong>기본 링크</strong>
          </a>
        } />
      </PanelGroup> : null}
      <PanelGroup tone="main" title="Main-Quiz" note="개념·방향별 반복">
        {bank?.usable ? <StudyCard lecture={lecture} bank={bank} />
          : <p className="panel-hint">아직 공개된 문제가 없습니다.</p>}
      </PanelGroup>
      </>
    );
  }
  return (
    <>
      <BankAdmin lecture={lecture} detail={detail} />
    </>
  );
}

function StudyCard({ lecture, bank, tools }: {
  lecture: Pick<LectureRef, "subject" | "runId">;
  bank: BankSummary;
  tools?: React.ReactNode;
}) {
  return (
    <>
      <ActionCard
        shape="is-key"
        hit={
          <Link className="panel-action-hit" to={bankHref(lecture)}>
            <strong>공부하기</strong>
            <small>{bank.seenQuestionCount}/{bank.studyQuestionCount}문항 봄 · 개념 {bank.conceptCount}개</small>
          </Link>
        }
        tools={tools}
      />
    </>
  );
}

const STATUS_LINE: Record<BankSummary["status"], string> = {
  linked: "문제은행 링크 저장됨 · Main-Quiz는 별도로 만들 수 있습니다",
  responded: "응답을 받았다 — 러너가 정리하기를 기다린다",
  building: "러너가 정리·검토하는 중",
  ready: "준비됨",
  invalid: "검증 오류가 있다 — 학생에게 열 수 없다",
  failed: "정리에 실패했다",
};

function conversationLink(value?: string) {
  try {
    const url = new URL(value || "");
    return url.protocol === "https:" && ["chatgpt.com", "chat.openai.com"].includes(url.hostname)
      && /^\/(?:g\/[^/]+\/)?(?:c|share)\/[^/]+/.test(url.pathname) ? url.href : "";
  } catch { return ""; }
}

function BankAdmin({ lecture, detail }: { lecture: Pick<LectureRef, "subject" | "runId">; detail: LectureDetail }) {
  const path = `${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const adminBase = `/api/admin/lectures/${path}`;
  const bank = detail.bank;
  const conversation = conversationLink(bank?.conversationUrl);
  const sources = detail.bankSources ?? [];
  const notes = sources.find((s) => s.kind === "notes_current");
  const [job, setJob] = useState<PrequizJob | null>(null);
  const [runner, setRunner] = useState<RunnerBeat | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [showLinks, setShowLinks] = useState(false);
  const [share, setShare] = useState("");
  const [mine, setMine] = useState("");
  const [showSetup, setShowSetup] = useState(false);

  const load = useCallback(() => {
    api<{ job: PrequizJob | null; runner: RunnerBeat | null }>(`${adminBase}/prequiz-job?kind=bank`)
      .then((answer) => {
        setJob(answer.job);
        setRunner(answer.runner);
      })
      .catch(() => {});
  }, [adminBase]);
  useEffect(load, [load]);

  const moving = jobMoving(job);
  const failureSuperseded = bank?.status === "ready" && Boolean(bank.builtAt)
    && Date.parse(bank.builtAt!) > Date.parse(job?.updatedAt || "");
  useEffect(() => {
    if (!moving) return;
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, [moving, load]);

  // 끝나면 강의 상세를 다시 읽는다 — 요약(문항 수·검토)이 거기서 온다.
  const wasMoving = useRef(false);
  useEffect(() => {
    if (wasMoving.current && !moving) bumpPreviewVersion();
    wasMoving.current = moving;
  }, [moving]);

  /** 기본은 사람이 전송한다. 자동전송을 고르면 확장이 전송까지 맡는다. */
  async function make(autoSend: boolean) {
    if (!notes) return;
    if (!extensionCompatible(extensionInputMinimum("bank", autoSend))) {
      setShowSetup(true);
      setError("아래 브리지 설치·업데이트 안내에서 최신 버전을 설치하고 이 페이지를 새로고침하세요.");
      return;
    }
    setBusy(autoSend ? "auto" : "make");
    setError("");
    try {
      // 서명 URL 은 수명이 짧아 누른 순간에 받는다.
      const files = [];
      for (const source of sources) {
        const { url } = await api<{ url: string }>(`/api/lectures/${path}/files/${source.assetId}`);
        files.push({ id: source.assetId, filename: source.filename, downloadUrl: absoluteUrl(url),
                     contentType: source.contentType });
      }
      await requestPreview({
        requestId: `${lecture.runId}-bank-${performance.now()}`,
        lectureId: `${lecture.subject}/${lecture.runId}`,
        provider: "chatgpt",
        mode: "bank",
        prompt: renderBankPrompt(detail, sources),
        files,
        autoSend,
      });
      setNote(autoSend
        ? "자동전송을 시작했습니다. 답변이 끝나면 공유·개인 링크를 각각 저장합니다."
        : "문제은행 링크용 ChatGPT 대화를 열었습니다. 직접 전송하면 공유·개인 링크를 각각 저장합니다.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy("");
    }
  }

  /** 문제은행 링크 생성과 분리된 CLI 출제 세션을 요청한다. */
  async function reorganize() {
    setBusy("again");
    setError("");
    try {
      const answer = await api<{ job: PrequizJob }>(`${adminBase}/prequiz-job?kind=bank`, {
        method: "POST",
        body: JSON.stringify({ force: true }),
      });
      setJob(answer.job);
      setNote("Main-Quiz 생성 작업을 요청했습니다. CLI가 별도 세션에서 출제·검증합니다.");
      bumpPreviewVersion();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function audit() {
    setBusy("audit");
    setError("");
    try {
      await api(`${adminBase}/bank/audit`, { method: "POST" });
      setNote("원본 누락 검증·객관식 보강을 요청했습니다. 현재 카드로 계속 공부할 수 있습니다.");
      load();
    } catch (cause) {
      setError((cause as Error).message);
    } finally { setBusy(""); }
  }

  async function saveLinks() {
    setBusy("links");
    setError("");
    try {
      await api(`${adminBase}/bank/links`, { method: "PUT",
        body: JSON.stringify({ shareUrl: share.trim(), conversationUrl: mine.trim() }) });
      setShowLinks(false);
      setNote("공유 링크와 개인 대화 주소를 저장했습니다.");
      bumpPreviewVersion();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(""); }
  }

  async function setOpen(open: boolean) {
    setBusy("open");
    setError("");
    try {
      await api(`${adminBase}/bank/open`, { method: "PUT", body: JSON.stringify({ open }) });
      bumpPreviewVersion();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy("");
    }
  }

  const review = bank?.reviewCounts;
  return (
    <>
      <PanelGroup tone="bank" title="문제은행 링크">
        <div className="panel-pair">
          <ActionCard
            shape="is-key"
            hit={bank?.shareUrl ? (
              <a className="panel-action-hit" href={bank.shareUrl} target="_blank" rel="noreferrer">
                <strong>기본 링크</strong>
              </a>
            ) : (
              <button className="panel-action-hit" disabled={Boolean(busy) || !notes || !extensionCompatible(extensionInputMinimum("bank", false))} onClick={() => void make(false)}>
                <strong>기본 링크</strong><small>{busy === "make" ? "여는 중…" : notes ? "만들기" : "올해 필기 대기"}</small>
              </button>
            )}
            tools={notes ? <PanelTool icon="↗" label="자동전송" hint="자료·프롬프트를 첨부하고 자동으로 전송한다"
              busy={busy === "auto"} disabled={Boolean(busy) || !extensionCompatible(extensionInputMinimum("bank", true))}
              onClick={() => void make(true)} /> : undefined}
          />
          {conversation ? <ActionCard shape="is-key" hit={
            <a className="panel-action-hit" href={conversation} title={conversation} target="_blank" rel="noopener noreferrer">
              <strong>개인 링크</strong>
            </a>
          } /> : <ActionCard shape="is-empty is-key" hit={
            <span className="panel-action-hit">
              <strong>개인 링크</strong><small>아직 없습니다</small>
            </span>
          } />}
        </div>
        <div className="panel-aside">
          {bank?.shareUrl || conversation ? <PanelTool icon="⟳" label="새로 만들기" hint="문제은행 새 대화에 자료·프롬프트를 넣고 직접 전송한다"
            busy={busy === "make"} disabled={Boolean(busy) || !notes || !extensionCompatible(extensionInputMinimum("bank", false))}
            onClick={() => void make(false)} /> : null}
          <PanelTool icon="🔗" label={showLinks ? "링크 접기" : bank?.shareUrl || conversation ? "링크 고치기" : "링크 넣기"} hint="문제은행 공유 링크·개인 링크 입력 (관리자)"
            active={showLinks} expanded={showLinks} disabled={Boolean(busy)} onClick={() => {
              if (!showLinks) { setShare(bank?.shareUrl || ""); setMine(bank?.conversationUrl || ""); }
              setShowLinks((value) => !value);
            }} />
        </div>
        {showLinks ? <div className="link-editor">
          <label className="link-editor-field"><span>기본 링크 — 공유 주소</span>
            <input value={share} placeholder="https://chatgpt.com/share/…" spellCheck={false}
              onChange={(event) => setShare(event.target.value)} />
          </label>
          <label className="link-editor-field"><span>개인 링크 — 생성 대화 주소</span>
            <input value={mine} placeholder="https://chatgpt.com/c/…" spellCheck={false}
              onChange={(event) => setMine(event.target.value)} />
          </label>
          <div className="link-editor-actions">
            <button className="is-primary" disabled={Boolean(busy)} onClick={() => void saveLinks()}>{busy === "links" ? "저장 중…" : "저장"}</button>
            <small>비우고 저장하면 지워집니다.</small>
          </div>
        </div> : null}
        {!bank?.shareUrl || showSetup ? <ExtensionSetup minimum={extensionInputMinimum("bank", true)} /> : null}
      </PanelGroup>
      <PanelGroup tone="main" title="Main-Quiz">
        {bank?.usable ? <StudyCard lecture={lecture} bank={bank} tools={
          <PanelTool icon="⟳" label="다시 만들기" hint="Main-Quiz를 별도 세션에서 다시 출제·검증한다"
            busy={busy === "again"} disabled={Boolean(busy) || moving || !notes} onClick={() => void reorganize()} />
        } /> : <ActionCard shape={`is-key${moving || !notes ? " is-empty" : ""}`} hit={
          <button className="panel-action-hit" disabled={Boolean(busy) || moving || !notes} onClick={() => void reorganize()}>
            <strong>Main-Quiz</strong>
            <small>{moving ? "준비 중…" : busy === "again" ? "요청 중…" : !notes ? "올해 필기 대기"
              : bank?.respondedAt ? "다시 만들기" : "만들기"}</small>
          </button>
        } />}
        {bank?.usable ? <>
          <div className="panel-aside">
            <PanelTool icon="⟳" label="누락 검증·객관식 보강" busyLabel="요청 중…"
              busy={busy === "audit"} disabled={Boolean(busy) || moving} onClick={() => void audit()} />
            <PanelTool icon={bank.open ? "◉" : "○"} label={bank.open ? "학생에게 닫기" : "학생에게 열기"}
              busy={busy === "open"} disabled={Boolean(busy)} onClick={() => void setOpen(!bank.open)} />
          </div>
          <BankCoverage value={bank.coverage} />
        </> : null}
        {bank?.revision ? <details className="panel-hint">
          <summary>CLI 검수 결과 — 자동 수정·보완 후 미해결 항목</summary>
          <p>저장된 응답과 원본 자료로 CLI가 검토·수정·누락 보완을 수행합니다. 아래 기록을 확인한 뒤 Main-Quiz 다시 만들기를 요청하세요.</p>
          <button className="is-quiet" onClick={() => void navigator.clipboard.writeText(
            "아래 CLI 검수 결과에 따라 로컬 문제은행을 검토·수정하고 누락을 보완해주세요. "
            + "저장된 응답과 원본 자료를 사용하고 웹 대화를 호출하지 마세요.\n\n"
            + JSON.stringify(bank.revision, null, 2)
          ).then(() => setNote("CLI 검수 기록을 복사했습니다."))
            .catch(() => setError("복사하지 못했습니다. 아래 검수 내용을 직접 복사하세요."))}>검수 기록 복사</button>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(bank.revision, null, 2)}</pre>
        </details> : null}
        {bank?.respondedAt ? (
          <div className="panel-hint">
            <Link to={`/admin/bank-cards/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`}>
              문항 검토·수정{bank.dropped?.length ? ` · 제외 ${bank.dropped.length}개` : ""}
              {review ? ` · 틀림 ${review.wrong} · 의심 ${review.doubt}` : ""}
            </Link>
          </div>
        ) : null}
        {bank && bank.status !== "linked" && (bank.status !== "ready" || review?.wrong || review?.doubt) ? (
          <p className="panel-hint">
            {STATUS_LINE[bank.status]}
            {bank.usable ? ` · ${bank.seenQuestionCount}/${bank.studyQuestionCount}문항 봄` : ""}
            {bank.status === "invalid" && bank.errorCount ? ` (${bank.errorCount}건)` : ""}
            {review ? ` · 외부지식 검토 틀림 ${review.wrong} · 의심 ${review.doubt}` : ""}
            {bank.usable ? (bank.open ? " · 학생에게 열림" : " · 아직 관리자만 본다") : ""}
            {bank.status === "failed" && bank.message ? ` — ${bank.message}` : ""}
          </p>
        ) : null}
        {/* 걸린 문항만 빼고 열었다(2026-10-05 관리자 지시). 무엇을 왜 뺐는지 남긴다 — 빠진 줄 모르면
            학생 화면의 문항 수가 응답보다 적은 것을 고장으로 읽는다. */}
        {bank?.dropped?.length ? (
          <details className="panel-hint">
            <summary>검증에 걸려 뺀 문항 {bank.dropped.length}개 — {bank.dropped.map((d) => d.questionId).join(", ")}</summary>
            <ul>
              {bank.dropped.map((d) => (
                <li key={d.questionId}>{d.errors.join(" · ")}</li>
              ))}
            </ul>
            <Link to={`/admin/bank-cards/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`}>제외된 문항 열고 수정하기</Link>
          </details>
        ) : null}
        {moving && job ? (
          <p className="panel-hint">
            정리 — {progressLine(job)}
            {runnerAlive(runner) ? "" : " · 러너가 꺼져 있다"}
          </p>
        ) : null}
        {job?.state === "failed" && !failureSuperseded ? <p className="notice is-error">{job.message}</p> : null}
      </PanelGroup>
      {note ? <p className="panel-hint">{note}</p> : null}
      {error ? <p className="notice is-error">{error}</p> : null}
    </>
  );
}
