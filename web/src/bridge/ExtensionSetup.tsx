import manifest from "../../../bridge/manifest.json";
import { EXTENSION_DOWNLOAD_URL, EXTENSION_STORE_URL, EXTENSION_STORE_VERSION } from "./protocol";
import { extensionCompatible, extensionInputMinimum, extensionPossible, extensionVersion } from "./previewBridge";
import { versionAtLeast } from "./version";
import { useMe } from "../useMe";

/** 스토어 공개판이 필요한 버전에 못 미치면 빌드에 포함된 최신판을 안내한다. */
export function ExtensionSetup({ minimum = extensionInputMinimum() }: { minimum?: string }) {
  const admin = Boolean(useMe()?.isAdmin);
  if (!extensionPossible() || extensionCompatible(minimum)) return null;
  const installed = extensionVersion();
  const storeReady = Boolean(EXTENSION_STORE_URL) && versionAtLeast(EXTENSION_STORE_VERSION, minimum);
  return (
    <div className="panel-steps">
      <p>{installed ? `설치된 브리지 ${installed}은 업데이트가 필요합니다.` : "예습·복습 대화를 만들려면 브리지를 설치해 주세요."}</p>
      {storeReady ? (
        <>
          <p><a href={EXTENSION_STORE_URL} target="_blank" rel="noreferrer">Chrome 웹스토어에서 브리지 {installed ? "업데이트" : "설치"}</a></p>
          <p>설치 후 Study EZ와 열려 있는 AI 대화 탭을 새로고침해 주세요.</p>
        </>
      ) : (
        <>
          <p>웹스토어 공개판({EXTENSION_STORE_VERSION})은 이 기능에 필요한 {minimum}보다 낮습니다.</p>
          <p><a href={EXTENSION_DOWNLOAD_URL} download>최신 브리지 {manifest.version} 내려받기</a></p>
          <ol>
            <li>받은 ZIP을 압축 해제합니다. 이미 수동 설치했다면 기존 폴더의 파일을 교체합니다.</li>
            <li><code>chrome://extensions</code>에서 개발자 모드를 켭니다.</li>
            <li>웹스토어에서 설치한 구버전 브리지는 끈 뒤, <b>압축해제된 확장 프로그램을 로드</b>로 압축 푼 폴더를 선택합니다. 이미 수동 설치한 브리지는 <b>새로고침</b>을 누릅니다.</li>
            <li>Study EZ와 열려 있는 AI 대화 탭을 새로고침합니다.</li>
          </ol>
        </>
      )}
      {/* 스토어판·사이트 ZIP은 학생용 사용자판이다. 관리자 기능은 저장소의 관리자판에서만 열린다. */}
      {admin ? <p>관리자 기능(공통 대화·Quiz Bank·자동전송)은 관리자판이 필요합니다. 저장소의 <code>bridge</code> 폴더를 압축해제된 확장 프로그램으로 로드하세요.</p> : null}
    </div>
  );
}
