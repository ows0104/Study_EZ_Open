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
import { BANK_PROMPT_VERSION, renderBankPrompt } from "./prompt";
import { BankCoverage } from "./BankCoverage";

/**
 * 캘린더 패널의 Quiz Bank 칸(2026-10-04).
 *
 *   관리자   ChatGPT 로 만들기 → (답이 끝나면 확장이 본문을 가져와 저장) → 러너가 정리·검토
 *            → 검토 결과를 보고 「학생에게 열기」
 *   학생     열린 은행이면 「공부하기」
 *
 * Main Quiz의 생성과 학습은 이 패널에서 처리한다.
 *
 * **「답 붙여넣기」는 확장이 못 읽는 자리를 위한 길이다**(2026-10-05 관리자 지시). 학교 계정(내부 워크스페이스)
 * ChatGPT 로 만든 답은 확장이 가져오지 못해 저장되지 않았다. 같은 저장 경로(`PUT …/bank-response`)로 넣으므로
 * 그 뒤는 확장으로 들어온 답과 똑같이 러너가 정리한다.
 */
export function BankPanel({ lecture, detail }: { lecture: Pick<LectureRef, "subject" | "runId">; detail: LectureDetail }) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const bank = detail.bank;
  if (!isAdmin) {
    if (!bank?.usable) return (
      <PanelGroup tone="main" title="Main-Quiz" note="강의 후 반복">
        <p className="panel-hint">아직 공개된 문제가 없습니다.</p>
      </PanelGroup>
    );
    return (
      <PanelGroup tone="main" title="Main-Quiz" note="개념·방향별 반복">
        {bank.shareUrl ? <ActionCard shape="is-key" hit={
          <a className="panel-action-hit" href={bank.shareUrl} target="_blank" rel="noreferrer">
            <strong>기본 링크</strong><small>ChatGPT 문제은행</small>
          </a>
        } /> : null}
        <StudyCard lecture={lecture} bank={bank} />
      </PanelGroup>
    );
  }
  return (
    <PanelGroup tone="main" title="Main-Quiz">
      <BankAdmin lecture={lecture} detail={detail} />
    </PanelGroup>
  );
}

function StudyCard({ lecture, bank }: { lecture: Pick<LectureRef, "subject" | "runId">; bank: BankSummary }) {
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
      />
    </>
  );
}

const STATUS_LINE: Record<BankSummary["status"], string> = {
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
  const [pasting, setPasting] = useState(false);
  const [pasted, setPasted] = useState("");
  const [pastedUrl, setPastedUrl] = useState("");
  const [showLinks, setShowLinks] = useState(false);
  const [share, setShare] = useState("");
  const [mine, setMine] = useState("");

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

  /** 자동 출제는 확장이 첨부·전송·응답 저장을 맡고 러너 검수로 이어진다. */
  async function make(autoSend: boolean) {
    if (!notes) return;
    if (!extensionCompatible(extensionInputMinimum("bank", autoSend))) {
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
        ? "자동 출제를 시작했습니다. 확장이 자료를 첨부·전송하고, 답변 저장 후 CLI 검수가 이어집니다."
        : "ChatGPT 탭을 열었습니다. 자료와 프롬프트를 확인하고 직접 전송하면 답변을 가져옵니다.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy("");
    }
  }

  /** 붙여 넣은 답을 저장한다 — 확장이 하던 저장과 같다. 끝 표시가 없으면 서버도 안 받으므로 먼저 말한다. */
  async function savePasted() {
    const raw = pasted.trim();
    if (!raw.includes("STUDYEZ_BANK_COMPLETE")) {
      setError("마지막 줄의 STUDYEZ_BANK_COMPLETE 가 없습니다. 답이 끝까지 나온 뒤 전체를 붙여 넣으세요.");
      return;
    }
    setBusy("paste");
    setError("");
    try {
      await api(`${adminBase}/bank-response`, {
        method: "PUT",
        body: JSON.stringify({ raw, conversationUrl: pastedUrl.trim() || conversation, promptVersion: BANK_PROMPT_VERSION }),
      });
      setPasting(false);
      setPasted("");
      setPastedUrl("");
      setNote("붙여 넣은 답을 저장했다. 러너가 정리·검토한다.");
      load();
      bumpPreviewVersion();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy("");
    }
  }

  /** 저장된 응답으로 다시 정리·검토한다. ChatGPT 는 안 다시 부른다. */
  async function reorganize() {
    setBusy("again");
    setError("");
    try {
      const answer = await api<{ job: PrequizJob }>(`${adminBase}/prequiz-job?kind=bank`, {
        method: "POST",
        body: JSON.stringify({ force: true }),
      });
      setJob(answer.job);
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

  if (!notes && !bank?.shareUrl) {
    return (
      <ActionCard
        shape="is-empty is-key"
        hit={
          <span className="panel-action-hit" title="Quiz Bank 는 올해 필기로 만든다">
            <strong>Main-Quiz</strong>
            <small>올해 필기 대기</small>
          </span>
        }
      />
    );
  }

  const review = bank?.reviewCounts;
  return (
    <>
      {bank?.usable ? <StudyCard lecture={lecture} bank={bank} /> : null}
      {bank?.usable ? <>
        <button disabled={Boolean(busy) || moving} onClick={() => void audit()}>
          {busy === "audit" ? "요청 중…" : "누락 검증·객관식 보강"}
        </button>
        <BankCoverage value={bank.coverage} />
      </> : null}
      <ActionCard
        shape="is-key"
        hit={bank?.shareUrl ? (
          <a className="panel-action-hit" href={bank.shareUrl} target="_blank" rel="noreferrer">
            <strong>기본 링크</strong><small>ChatGPT 문제은행</small>
          </a>
        ) : (
          <button className="panel-action-hit" disabled={Boolean(busy) || moving || !extensionCompatible(extensionInputMinimum("bank", true))} onClick={() => void make(true)}>
            <strong>{busy === "auto" ? "자동 출제 시작 중…" : "자동 출제"}</strong>
            <small>
              {sources.some((s) => s.kind === "jokbo") ? "필기 + 족보" : "필기"} · 전송·저장·CLI 검수
            </small>
          </button>
        )}
        tools={
          <>
            {bank?.shareUrl ? <PanelTool icon="⟳" label="새로 만들기" hint="자료를 첨부하고 새 문제은행을 자동 출제한다"
              disabled={Boolean(busy) || moving || !notes || !extensionCompatible(extensionInputMinimum("bank", true))}
              onClick={() => void make(true)} /> : null}
            <PanelTool icon="↗" label="직접 전송" hint="자료·프롬프트만 넣고 전송은 직접 한다"
                       busy={busy === "make"} disabled={Boolean(busy) || moving || !extensionCompatible()}
                       onClick={() => void make(false)} />
            <PanelTool icon="⎘" label="답 붙여넣기" hint="확장이 못 가져온 ChatGPT 답을 직접 붙여 넣는다"
                       active={pasting} expanded={pasting} disabled={Boolean(busy) || moving}
                       onClick={() => setPasting((v) => !v)} />
            {bank ? (
              <PanelTool icon="⟳" label="다시 정리" hint="저장된 응답으로 정리·검토만 다시 한다"
                         busy={busy === "again"} disabled={Boolean(busy) || moving} onClick={() => void reorganize()} />
            ) : null}
            {bank?.usable ? (
              <PanelTool icon={bank.open ? "◉" : "○"} label={bank.open ? "학생에게 닫기" : "학생에게 열기"}
                         busy={busy === "open"} disabled={Boolean(busy)} onClick={() => void setOpen(!bank.open)} />
            ) : null}
          </>
        }
      />
      {bank ? <div className="panel-aside">
        <PanelTool icon="🔗" label={showLinks ? "수정 접기" : "수정"} hint="문제은행 공유 링크·개인 링크 수정 (관리자)"
          active={showLinks} expanded={showLinks} disabled={Boolean(busy)} onClick={() => {
            if (!showLinks) { setShare(bank.shareUrl || ""); setMine(bank.conversationUrl || ""); }
            setShowLinks((value) => !value);
          }} />
      </div> : null}
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
          <button disabled={Boolean(busy)} onClick={() => void saveLinks()}>{busy === "links" ? "저장 중…" : "저장"}</button>
          {conversation ? <a href={conversation} target="_blank" rel="noopener noreferrer">개인 링크에서 응답 수정</a> : null}
        </div>
      </div> : null}
      <ExtensionSetup minimum={extensionInputMinimum("bank", true)} />
      {bank?.revision ? <details className="panel-hint">
        <summary>CLI 검수 결과 — 생성한 ChatGPT 응답 수정 필요</summary>
        <p>대화를 열어 아래 검수 내용을 전달하고, 수정된 전체 응답을 답 붙여넣기로 저장하세요.</p>
        <button className="is-quiet" onClick={() => void navigator.clipboard.writeText(
          "아래 CLI 검수 결과에 따라 기존 문제은행을 수정해주세요. 통과한 문항과 ID는 보존하고, "
          + "수정된 전체 응답을 STUDYEZ_BANK_COMPLETE까지 출력해주세요.\n\n"
          + JSON.stringify(bank.revision, null, 2)
        ).then(() => setNote("검수 결과와 수정 요청을 복사했습니다."))
          .catch(() => setError("복사하지 못했습니다. 아래 검수 내용을 직접 복사하세요."))}>수정 요청 복사</button>
        <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(bank.revision, null, 2)}</pre>
      </details> : null}
      {pasting ? (
        <div className="bank-paste">
          <label>생성 대화 주소
            <input type="url" value={pastedUrl} placeholder={conversation || "https://chatgpt.com/c/… (선택)"}
                   onChange={(event) => setPastedUrl(event.target.value)} />
          </label>
          <textarea
            rows={8}
            value={pasted}
            placeholder="ChatGPT 답 전체를 붙여 넣으세요 — 「## 1. Concept Map」부터 마지막 줄 STUDYEZ_BANK_COMPLETE 까지"
            onChange={(event) => setPasted(event.target.value)}
          />
          <div className="bank-paste-actions">
            <small>{pasted ? `${Math.round(pasted.length / 1024)}KB` : ""}</small>
            <button className="is-quiet" disabled={busy === "paste"} onClick={() => setPasting(false)}>취소</button>
            <button disabled={busy === "paste" || !pasted.trim()} onClick={() => void savePasted()}>
              {busy === "paste" ? "저장하는 중…" : "저장하고 정리"}
            </button>
          </div>
          {bank ? <small className="panel-hint">저장하면 지금 은행을 이 답으로 새로 만든다.</small> : null}
        </div>
      ) : null}
      {bank ? (
        <div className="panel-hint">
          <Link to={`/admin/bank-cards/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`}>
            문항 검토·수정{bank.dropped?.length ? ` · 제외 ${bank.dropped.length}개` : ""}
            {review ? ` · 틀림 ${review.wrong} · 의심 ${review.doubt}` : ""}
          </Link>
        </div>
      ) : null}
      {bank ? (
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
      {job?.state === "failed" ? <p className="notice is-error">{job.message}</p> : null}
      {note ? <p className="panel-hint">{note}</p> : null}
      {error ? <p className="notice is-error">{error}</p> : null}
    </>
  );
}
