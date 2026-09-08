"""추출한 이미지를 종·표본에 매핑한다.

    uv run --python 3.13 python scripts/map_images.py

입력: data/image_manifest.json, data/species.json, data/specimens.json
출력: data/images.json          이미지별 species_id / specimen_id / 신뢰도
      data/images_unmapped.csv  사람이 봐야 하는 것만 추림

원본 라벨에 학명 오타가 많아(Ascaris lumbricodies, Taneia solium …)
정확 일치 -> alias -> 퍼지 -> 속명(genus) 순으로 단계적으로 매칭한다.
"""

import csv
import difflib
import json
import os
import re
import sys
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# ── 들여놓지 않는 출처
#
# **사진은 멀쩡한데 라벨을 못 믿는다.** `extract_summary_pdf.py`가 뽑아 놓은
# 것들은 깨끗하고 글자도 지워져 있지만, 종을 붙이는 자리에서 무너졌다.
# 셋 다 사진의 3분의 1에서 절반이 「회충 성충」 한 라벨로 쏟아졌다 — 「회충」이
# 흔한 낱말이라 못 붙인 것들의 쓰레기통이 됐다. 믿는 출처 셋(실제실습본·전민서·
# 실습사진통합)은 같은 자리에서 쏠림이 4%다.
#
# 라벨이 틀린 사진은 흐린 사진보다 나쁘다. 흐린 사진은 어려운 문제일 뿐이지만
# 틀린 라벨은 맞게 고른 사람을 틀렸다고 채점한다. 그래서 고칠 때까지 뺀다.
#
# 매니페스트는 `data/`에 그대로 있다. 표제와 사진을 잇는 자리(포스터 한 칸의
# 표제가 그 칸 사진들만 거느리게 하는 것)를 고치고 이 표에서 지우면 그대로
# 다시 들어온다. 확인은 `scripts/label_sheet.py`가 만드는 대조표로 한다.
# 2026-09-07: 셋 다 들여놓았다. 막고 있던 것이 둘이었고 둘 다 고쳤다.
#
#   ① `norm`이 한글을 지워서 색인에 빈 키가 생겼고, 한글 이름표가 죄다 한
#      종으로 붙었다(506장 중 217장이 회충). → `norm`이 한글을 남기고,
#      빈 키는 색인에 안 들어간다.
#   ② 표본 종류(성충/절편/육안)를 정할 단서가 원본에 아예 없었다. 글에도
#      없고 픽셀로도 안 됐다 — 육안 판정 정확도 12%, 조직 대 충체는 72%로
#      "무조건 충체"(73%)보다 못했다. → 147장을 눈으로 보고
#      `image_overrides.json`에 표본을 직접 적었다.
#
# 지금 쏠림은 이지석 15% · 신은주 8% · 필기본 9%로, 믿는 출처(4~5%)와
# 족보(16%) 사이다.
HELD = {}

# 보류를 푸는 스위치. **고치려면 붙여 봐야 하는데**, 붙이려면 배포용
# `images.json`을 덮어써야 한다. 그 사이에 빌드가 돌면 라벨을 못 믿는 사진이
# 그대로 나간다. 환경변수로만 열어 두어서, 진단하는 사람이 자기가 뭘 하는지
# 알고 켜게 한다.
#
#     SPOTTER_UNHOLD=1 uv run ... python scripts/map_images.py
if os.getenv("SPOTTER_UNHOLD"):
    HELD = {}

# ── 일부만 들여놓는 출처
#
# **실제실습본은 말라리아만 쓴다.**
#
# 사진 자체는 이 저장소에서 제일 크고(짧은변 중앙 808px) 라벨 쏠림도 4%로
# 가장 고르다. 다만 잘림이 지저분하고(옆 슬라이드가 비쳐 든다) 손그림
# 스케치까지 섞여 있어서, 다른 출처로 갈음할 수 있는 자리는 갈음한다.
#
# **말라리아만 남기는 것은 비율 때문이다.** 통째로 빼면 말라리아 문항이
# 6.0%에서 3.3%로 반토막 나는데, 족보 기준 출제 비율이 7%다. 도말과
# 조직절편을 이만큼 들고 있는 출처가 여기뿐이라 그 자리만 살린다.
#
# 종의 `group` 으로 가른다 — 열원충 다섯 종이 이 분류군이다.
PARTIAL = {"practical": {"말라리아"}}

# 반대쪽 스위치. 출처를 **빼고** 어떻게 되는지 보려는 것이다.
#
#     SPOTTER_HOLD=practical uv run ... python scripts/map_images.py
#
# 「실제실습본 없이도 되나」 같은 물음은 재 봐야 답이 나오는데, 재려고 코드를
# 고쳤다 되돌리면 그 사이에 잘못된 상태로 빌드가 돌 수 있다.
for _name in (os.getenv("SPOTTER_HOLD") or "").split(","):
    _name = _name.strip()
    if _name:
        HELD[_name] = "SPOTTER_HOLD 로 잠시 뺌"

# 표본 유형 판별 신호. 순서가 곧 우선순위다.
TISSUE = ["h&e", "gms", "section", "조직", "liver", "brain", "intestine",
          "spleen", "dog lung", "cerebral", "heart", "근육", "muscle", "피부"]
GROSS = ["gross", "육안", "demo"]
SMEAR = ["smear", "도말", "microfilaria", "trypomastigote"]
# 영구표본 마운트 신호 — 있으면 '충체'
MOUNT = ["jelly", "ac stain", "acetocarmine", "carmine", "unstained", "mount",
         "trichrome", "ih stain", "diff-quik", "diff-quick", "giemsa", "maf",
         "수컷", "암컷", "male", "female", "promastigote", "trophozoite", "cyst"]

# 표본 선택용 키워드: specimen_id -> 라벨에 나타나면 가점되는 토큰
STAGE_HINTS = {
    # "!토큰"은 그 토큰이 있으면 탈락시키는 부정 조건.
    # "불수정란"은 "수정란"을 부분문자열로 포함하므로 반드시 필요하다.
    "ascaris_fertilized_egg": ["수정란", "fertilized", "!불수정", "!unfertilized"],
    "ascaris_unfertilized_egg": ["불수정란", "unfertilized"],
    "strongyloides_filariform": ["filariform", "사상"],
    "strongyloides_rhabditoid": ["rhabditoid", "간상"],
    "trichinella_larva_wholemount": ["ac stain", "ac ", "acetocarmine"],
    "trichinella_encysted_larva": ["h&e", "section", "근육", "muscle"],
    "paragonimus_brain_section": ["cerebral", "brain", "뇌"],
    "paragonimus_lung_section": ["lung", "dog"],  # "폐"는 폐흡충 자체에 걸려 못 씀
    "diphyllobothrium_scolex": ["scolex", "두절"],
    "diphyllobothrium_gravid_proglottid": ["proglottid", "편절"],
    "taenia_solium_scolex": ["scolex", "두절"],
    "taenia_solium_gravid_proglottid": ["proglottid", "편절"],
    "taenia_saginata_scolex": ["scolex", "두절"],
    "taenia_saginata_gravid_proglottid": ["proglottid", "편절"],
    "cysticercus_muscle_section": ["section", "h&e", "muscle", "근육"],
    "cysticercus_wholemount": ["whole", "!section"],
    "entamoeba_histolytica_trophozoite": ["trophozoite", "영양형"],
    "entamoeba_histolytica_cyst": ["cyst", "포낭"],
    "entamoeba_histolytica_colon_section": ["h&e", "section"],
    "giardia_trophozoite": ["trophozoite", "영양형"],
    "giardia_cyst": ["cyst", "포낭"],
    "leishmania_promastigote": ["promastigote", "diff-quik", "major"],
    "leishmania_amastigote_liver": ["amastigote", "liver", "h&e", "donovani"],
    "toxoplasma_tachyzoite": ["tachyzoite", "giemsa"],
    "toxoplasma_brain_section": ["bradyzoite", "brain", "h&e", "뇌"],
    "pneumocystis_gms": ["gms"],
    "pneumocystis_diffquik": ["diff-quik", "diff-quick"],
    "cryptosporidium_intestine_section": ["h&e", "intestine", "section"],
    "cryptosporidium_oocyst_maf": ["maf", "oocyst"],
    "pfalciparum_thin_smear": ["thin"],
    "pfalciparum_thick_smear": ["thick"],
    "pvivax_thin_smear": ["thin"],
    "pvivax_thick_smear": ["thick"],
    "malaria_spleen_section": ["spleen", "비장"],
    "malaria_brain_section": ["brain", "뇌"],
    "trypanosoma_cruzi_trypomastigote": ["trypomastigote", "smear"],
    "trypanosoma_cruzi_heart_section": ["heart", "심근", "section"],
    "clonorchis_liver_section": ["h&e", "liver", "section"],
    "fasciola_liver_section": ["h&e", "section"],
    "neodiplostomum_intestine_section": ["h&e", "section"],
    "sarcoptes_skin_section": ["h&e", "section", "피부"],
    "sarcoptes_wholemount": ["whole", "mount"],
}


def norm(s):
    """이름 하나를 견줄 수 있는 꼴로. **한글과 숫자를 남긴다.**

    예전에는 `[^a-z]`라 알파벳만 남았다. 그래서 「회충」·「구충」·「편충」이
    전부 빈 문자열이 되었고, 색인을 세울 때 `exact[""] = 첫 번째 종`이 생겨
    **한글만 적힌 이름표가 죄다 그 한 종으로 붙었다.** 정리본에서 뽑은
    사진 506장 중 217장이 회충이 된 것이 이것이다 — 캡션이 「구충」이어도
    회충이 됐다.

    엑셀에서 온 것들은 학명을 같이 들고 있어서 이 고장을 안 겪었고, 그래서
    오래 안 보였다.
    """
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def norm_latin(s):
    """학명만 남긴다. `norm`이 한글을 남기게 되면서 필요해졌다.

    「Taenia sp. [유무구조충] 3」은 학명 쪽만 보면 「Taenia spp」와 닮았는데,
    한글이 섞인 채로 견주면 길이에 눌려 안 닮은 것이 된다. 실제로 그 여섯
    장이 아무 종에도 안 붙었다.
    """
    return re.sub(r"[^a-z]", "", (s or "").lower())


def norm_sep(s):
    """`norm`과 같되 **낱말 사이를 빈칸으로 남긴다.**

    품고 있는지 볼 때 필요하다. 다 붙여 버리면 「소장 회충」이 「소장회충」이
    되어 「회충」 앞에 한글이 오고, 앞 경계를 보는 규칙이 헛돈다.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z가-힣]", " ", (s or "").lower())).strip()


def latin_from(text):
    """'광절열두조충 (Diphyllobothrium latum)' 에서 학명만 뽑는다."""
    out = []
    for m in re.finditer(r"\(([^)]*)\)", text or ""):
        inner = m.group(1)
        for mm in re.finditer(r"\b([A-Z][a-z]{2,})\s+([a-z]{3,})\b", inner):
            out.append(f"{mm.group(1)} {mm.group(2)}")
    for mm in re.finditer(r"\b([A-Z][a-z]{2,})\s+([a-z]{3,})\b", text or ""):
        out.append(f"{mm.group(1)} {mm.group(2)}")
    return out


def build_index(species):
    exact, genus = {}, defaultdict(set)
    for s in species:
        keys = [s["scientific_name"], s["name_ko"]] + s.get("aliases", [])
        for k in keys:
            if not k:
                continue
            # **빈 키를 절대 넣지 않는다.** 넣으면 그 자리가 만능 열쇠가 되어,
            # 견줄 것이 없는 이름표가 전부 한 종으로 붙는다. `norm`을 고쳐서
            # 지금은 안 생기지만, 이 한 줄이 없으면 다음에 `norm`이 바뀔 때
            # 같은 고장이 조용히 돌아온다.
            if not norm(k):
                continue
            exact.setdefault(norm(k), s["id"])
            g = k.split()[0]
            if re.match(r"^[A-Z][a-z]{2,}$", g):
                genus[norm(g)].add(s["id"])
    return exact, genus


# 포스터·슬라이드에서 뽑은 출처. 이쪽은 `name_sub`가 **쪽(또는 칸) 표제**라
# 사진 자신의 이름표가 아니다.
FROM_PDF = ("jiseok", "eunju", "note")


def _ladder(cands, exact, genus, keys_norm, ko_keys):
    """이름표 몇 개를 놓고 종을 찾는다. 정확 -> 부분일치 -> 퍼지 -> 속명."""
    for c in cands:
        if not c:
            continue
        c = re.split(r"[,(]", c)[0].strip()
        for n in (norm(c), norm_latin(c)):
            # 한글이 섞인 이름표는 두 벌로 본다 — 통째로, 그리고 학명만.
            if n and n in exact:
                return exact[n], "exact"

    # 한글 이름은 **품고 있는 것**으로 찾는다.
    #
    # 이름표가 「회충 성충」·「구충 두절」처럼 종 이름 뒤에 부위·단계를 달고
    # 오는 일이 흔한데, 그건 정확 일치로는 안 잡힌다. 예전에는 이런 것들이
    # `norm`이 다 지워 버린 빈 문자열로 우연히 맞고 있었다.
    #
    # **긴 이름부터 본다.** 「고래회충」은 「회충」을 품고 있어서, 짧은 것을
    # 먼저 보면 고래회충 사진이 회충이 된다.
    for c in cands:
        n = norm_sep(c or "")
        if not n.strip():
            continue
        for key in ko_keys:                     # 긴 것부터 정렬돼 있다
            at = n.find(key)
            # **앞이 한글이면 다른 낱말이다.** 「유무구조충」은 「무구조충」을
            # 품고 있지만 "유구조충인지 무구조충인지 모름"이라는 뜻이고,
            # 실제로 실제실습본이 「Taenia sp. [유무구조충]」이라 적어 둔다.
            # 앞 경계를 안 보면 그 여섯 장이 무구조충으로 붙는다.
            # 뒤는 안 본다 — 「회충성충」처럼 붙여 쓴 것도 받아야 한다.
            if at >= 0 and (at == 0 or not re.match(r"[가-힣]", n[at - 1])):
                return exact[key], "부분일치"

    for c in cands:
        if not c:
            continue
        head = re.split(r"[,(]", c)[0]
        for n in (norm(head), norm_latin(head)):
            if len(n) < 6:
                continue
            hit = difflib.get_close_matches(n, keys_norm, n=1, cutoff=0.82)
            if hit:
                return exact[hit[0]], "fuzzy"

    ambiguous = False
    for c in cands:
        for g in re.findall(r"\b([A-Z][a-z]{2,})\b", c or ""):
            ids = genus.get(norm(g))
            if not ids:
                continue
            if len(ids) == 1:
                return next(iter(ids)), "genus"
            ambiguous = True       # 아는 속인데 종까지 못 좁혔다
    return None, ("속만 맞음" if ambiguous else None)


def match_species(rec, exact, genus, keys_norm, ko_keys):
    """이름표에서 종을 찾는다. (species_id, 방법) 반환.

    **가까운 글을 먼저 끝까지 본다.** 정리본에서 뽑은 사진은 `name_ko`가
    사진 옆에 적힌 것이고 `name_sub`는 그 칸 머리의 표제(또는 쪽 제목)다.
    표제를 먼저 보면 한 쪽에 여러 종이 선 포스터에서 표제 하나가 그 쪽 사진
    전부를 삼킨다 — 실제로 캡션이 「구충」·「편충」인 사진까지 회충으로
    붙어서, 새 출처 506장 중 217장이 회충 한 종으로 몰렸다.

    **끝까지가 중요하다.** 예전에는 단계마다(정확 -> 부분일치 -> 퍼지) 가까운
    것과 먼 것을 함께 훑었다. 그러면 순서가 「가까운 것 먼저」가 아니라
    「강하게 맞는 것 먼저」가 된다 — 먼 쪽의 정확 일치가 가까운 쪽의 부분
    일치를 이긴다. 이지석 실습1 p2가 그렇게 틀렸다. 사진 옆에는 「구충」이라
    적혀 있고 쪽 제목이 「편충」인데, **「구충」은 종이 아니라 표본 답 라벨**
    이라 종 색인에 없었다(종은 두비니구충·아메리카구충이다). 그래서 정확
    일치 단계에서 쪽 제목의 「편충」이 먼저 걸렸고, 구충란 석 장이 편충란이
    되어 나갔다 — 학생이 「이거 구충임」이라고 제보할 때까지.

    지금은 가까운 것으로 사다리를 끝까지 타 보고, 그래도 못 찾을 때만 먼
    것으로 넘어간다. 「구충」은 색인에 별칭으로 넣었다(`Hookworm`이 이미 그
    자리에 있었다).

    엑셀에서 온 것은 순서를 그대로 둔다. 거기 `name_sub`는 같은 칸의 부제라
    멀리 있는 글이 아니고, 바꾸면 잘 붙던 것이 흔들린다.
    """
    if rec.get("source") not in FROM_PDF:
        cands = ([rec["name_en"]] + latin_from(rec["name_sub"])
                 + latin_from(rec["name_ko"]) + [rec["name_sub"], rec["name_ko"]])
        return _ladder(cands, exact, genus, keys_norm, ko_keys)

    near = [rec["name_en"]] + latin_from(rec["name_ko"]) + [rec["name_ko"]]
    far = latin_from(rec["name_sub"]) + [rec["name_sub"]]
    sid, how = _ladder(near, exact, genus, keys_norm, ko_keys)
    if sid:
        return sid, how
    if how == "속만 맞음":
        # **가까운 이름표가 이미 종을 부르고 있다.** 좁히지 못했을 뿐이지
        # 다른 항목 이야기가 아니므로, 먼 글로 넘어가면 안 된다. 이지석
        # 실습4 p2가 그랬다 — 사진 위 표제가 「5. Plasmodium spp. (열원충)」
        # 인데 속만으로는 네 종 중 하나를 못 고르니, 쪽 제목 「4. Balantidium
        # coli (대장섬모충)」로 넘어가 말라리아 도말 두 장이 대장섬모충이
        # 됐다. 못 고르면 비워 두는 편이 낫다.
        return None, None
    return _ladder(far, exact, genus, keys_norm, ko_keys)


def is_egg_sheet(sheet, topic=None):
    """실제실습본은 시트가 하나뿐이라 PDF 섹션(topic)으로 충란 여부를 판단한다."""
    if topic:
        return topic == "충란"
    return "충란" in sheet or "egg" in sheet.lower()


def pick_type(blob, sheet, topic=None):
    """라벨·시트·섹션으로 표본 유형을 정한다. 못 정하면 None."""
    if any(t in blob for t in GROSS):
        return "gross"
    if any(t in blob for t in TISSUE):
        return "조직"
    if any(t in blob for t in SMEAR):
        return "혈액도말"
    if is_egg_sheet(sheet, topic):
        return "충란"
    if topic and topic != "충란":
        # 충란 섹션이 아닌 실제실습본 사진은 조직 신호가 없으면 영구표본이다
        return "충체"
    if any(t in blob for t in MOUNT):
        return "충체"
    return None


def main():
    species = json.load(open(os.path.join(DATA, "species.json"), encoding="utf-8"))
    specimens = json.load(open(os.path.join(DATA, "specimens.json"), encoding="utf-8"))
    manifest = json.load(open(os.path.join(DATA, "image_manifest.json"), encoding="utf-8"))
    # PDF에서 뽑은 것들. `image_manifest.json`(엑셀에서 뽑은 것)과 모양이 같아서
    # 그대로 이어 붙이면 아래 로직이 구분 없이 다룬다. 엑셀에만 있는 칸 몇 개만
    # 채워 준다.
    #
    # **파일이 없으면 조용히 넘어간다.** 정리본을 아직 안 뽑았거나 한 출처를
    # 빼 보는 중일 수 있고, 그때 여기서 죽으면 나머지까지 못 만든다.
    for name in ("practical", "jiseok", "eunju", "note"):
        if name in HELD:
            print(f"  {name}_manifest.json 건너뜀 — {HELD[name]}")
            continue
        path = os.path.join(DATA, f"{name}_manifest.json")
        if not os.path.exists(path):
            continue
        extra = json.load(open(path, encoding="utf-8"))
        for r in extra:
            r.setdefault("row", r.get("page", 0))
            r.setdefault("sha1", "")
            r.setdefault("duplicate_of", None)
            r.setdefault("bytes", 0)
        print(f"  {name}_manifest.json {len(extra)}장")
        manifest = manifest + extra

    ov_path = os.path.join(DATA, "image_overrides.json")
    overrides = {}
    if os.path.exists(ov_path):
        overrides = {k: v for k, v in
                     json.load(open(ov_path, encoding="utf-8")).items()
                     if not k.startswith("_")}

    by_specimen_species = {x["id"]: x["species_id"] for x in specimens}
    exact, genus = build_index(species)
    keys_norm = list(exact.keys())
    # 한글 이름만, 긴 것부터. `부분일치` 단계가 이 차례대로 훑는다 —
    # 「고래회충」이 「회충」보다 먼저 걸려야 한다.
    ko_keys = sorted((k for k in exact if re.search(r"[가-힣]", k)), key=len, reverse=True)
    by_species = defaultdict(list)
    for x in specimens:
        by_species[x["species_id"]].append(x)
    sp_by_id = {s["id"]: s for s in species}

    out, stats = [], Counter()
    for rec in manifest:
        # 정리본에서 뽑은 사진은 종 이름이 표제에 있고 **표본을 가르는 말은
        # 캡션에 있다** — 「식도 단면 -> single cell lining」의 '단면'이 그것이다.
        # 그 칸(`features`)이 없으면 회충인 줄은 아는데 성충인지 절편인지를
        # 못 골라서 문항으로 못 쓴다.
        #
        # **엑셀에서 온 것에는 안 넣는다.** 거기 `features`는 감별점을 길게 적어
        # 둔 칸이라 넣으면 `pick_type`이 엉뚱한 유형을 집는다 — 실제로 넣었더니
        # 전민서 쪽이 380장에서 353장으로 줄었다.
        parts = [rec["name_ko"], rec["name_sub"], rec["name_en"],
                 rec["stage"], rec["sheet"]]
        if rec.get("source") in ("jiseok", "eunju", "note"):
            parts.append(rec.get("features") or "")
        blob = " ".join(parts).lower()
        if rec.get("species_hint"):
            # 실제실습본은 페이지 제목을 종 테이블로 검증해 붙였으므로 그대로 신뢰한다
            sid, how = rec["species_hint"], "heading"
        else:
            sid, how = match_species(rec, exact, genus, keys_norm, ko_keys)
        row = dict(rec)
        row["species_id"] = sid
        row["match_method"] = how
        row["specimen_id"] = None
        row["confidence"] = "none"
        row["review_reason"] = ""

        # 일부만 들여놓는 출처는 여기서 거른다. **종을 붙인 뒤에** 봐야 한다 —
        # 무슨 분류군인지는 종이 정해져야 알 수 있다.
        keep = PARTIAL.get(rec.get("source"))
        if keep is not None:
            group = (sp_by_id.get(sid) or {}).get("group")
            if group not in keep:
                stats["일부만 들여놓음"] += 1
                # **`kind` 로 표시해 둔다.** 그냥 `continue` 만 하면 뒤에 도는
                # override 단계가 표본을 다시 붙여서 되살아난다 — 실제로
                # 99장이 그렇게 새어 나왔다. `quiz_usable` 은 `kind == "photo"`
                # 를 요구하므로 이 표시가 끝까지 남는다.
                row["kind"] = "held"
                row["review_reason"] = (
                    f"{rec['sheet']}에서는 {'·'.join(sorted(keep))}만 쓴다")
                out.append(row)
                continue

        if not sid:
            stats["종 미매칭"] += 1
            row["review_reason"] = "종을 찾지 못함"
            out.append(row)
            continue

        pool = by_species[sid]
        if not pool:
            stats["표본 없음"] += 1
            row["review_reason"] = f"{sp_by_id[sid]['name_ko']}에 등록된 표본이 없음"
            out.append(row)
            continue

        # 성별 토큰은 유형 신호가 아니므로 혼재 판정에서 뺀다.
        # gross 신호가 있으면 gross로 확정하고 혼재로 보지 않는다.
        mount_sig = [t for t in MOUNT if t not in ("수컷", "암컷", "male", "female")]
        mixed = (not any(t in blob for t in GROSS)
                 and any(t in blob for t in TISSUE)
                 and any(t in blob for t in mount_sig + SMEAR))
        mixed = mixed or bool(re.search(r"\d\s*번째", blob))
        want = pick_type(blob, rec["sheet"], rec.get("topic"))
        typed = [x for x in pool if x["specimen_type"] == want] if want else []
        if typed:
            cands = typed
        else:
            # 유형을 못 정했으면 명시 신호가 필요한 유형(gross)과,
            # 충란 시트가 아닌데 충란인 후보를 제외한다
            drop = {"gross"}
            if not is_egg_sheet(rec["sheet"], rec.get("topic")):
                drop.add("충란")
            cands = [x for x in pool if x["specimen_type"] not in drop] or pool
            if want and not typed:
                row["review_reason"] = f"라벨은 {want}로 보이나 해당 유형 표본이 없음. "

        if len(cands) == 1:
            row["specimen_id"] = cands[0]["id"]
            row["confidence"] = "high" if typed else "medium"
            stats["확정" if typed else "유형추정"] += 1
            if mixed and len(pool) > 1:
                row["confidence"] = "low"
                row["review_reason"] += "한 행에 여러 표본 유형이 섞여 있음"
                stats["확정" if typed else "유형추정"] -= 1
                stats["사람 확인 필요"] += 1
        else:
            scored = []
            for x in cands:
                hints = STAGE_HINTS.get(x["id"], [])
                neg = [h[1:] for h in hints if h.startswith("!")]
                pos = [h for h in hints if not h.startswith("!")]
                if any(h in blob for h in neg):
                    score = -1
                else:
                    score = sum(1 for h in pos if h in blob)
                scored.append((score, x))
            scored.sort(key=lambda t: -t[0])
            best, second = scored[0], scored[1] if len(scored) > 1 else (0, None)
            if best[0] > 0 and best[0] > second[0]:
                row["specimen_id"] = best[1]["id"]
                row["confidence"] = "high"
                stats["확정"] += 1
            else:
                row["specimen_id"] = scored[0][1]["id"]
                row["confidence"] = "low"
                row["review_reason"] += (
                    f"{sp_by_id[sid]['name_ko']}의 표본 후보 {len(cands)}개 중 "
                    "라벨만으로는 구분 불가: " + ", ".join(x["id"] for _, x in scored)
                )
                stats["사람 확인 필요"] += 1
        out.append(row)

    # 사람이 직접 보고 판정한 결과를 덮어쓴다
    spec_ids = {x["id"] for x in specimens}
    applied, unknown = 0, []
    for row in out:
        key = f'{row["source"]}/{row["sheet"]}/{row["cell"]}'
        if key not in overrides:
            continue
        val = overrides[key]
        if val == "exclude":
            # 표본병·접시에 종 이름이 적혀 있어 정답이 노출되는 사진
            row["kind"] = "answer_visible"
            row["confidence"] = "high"
            row["review_reason"] = "표본에 정답이 적혀 있어 문제로 쓰지 않음"
        elif val == "diagram":
            row["specimen_id"] = None
            row["kind"] = "diagram"
            row["confidence"] = "high"
            row["review_reason"] = "모식도·생활사 그림 (표본 사진 아님)"
        elif val == "compare":
            # **두 종을 한 화면에 나란히 놓고 견주는 사진.** 필기본에는
            # 「분선충은 M자, 구충은 뾰족」처럼 감별점을 가르쳐 주려고 둘을
            # 붙여 놓은 자리가 있다. 표본 하나를 붙이면 어느 쪽을 붙여도
            # 틀린 것이 되고 — 실제로 분선충·구충 유충 꼬리 비교 사진이
            # 두비니구충 성충으로 나갔다 — 「다음 기생충은?」이라고 물을
            # 수도 없다. 화면에 답이 둘 있기 때문이다.
            row["specimen_id"] = None
            row["kind"] = "compare"
            row["confidence"] = "high"
            row["review_reason"] = "두 종을 나란히 놓고 견주는 사진 (한 종을 묻는 문제로 쓸 수 없음)"
        elif val in spec_ids:
            row["specimen_id"] = val
            row["confidence"] = "high"
            row["review_reason"] = ""
        else:
            unknown.append((key, val))
            continue
        applied += 1
    for key, val in unknown:
        print(f"  ! override 대상 표본이 없음: {key} -> {val}")

    # 문제로 쓸 수 있는 이미지인지 판정 (해상도 + 모식도 여부)
    try:
        from PIL import Image, ImageFilter
        for row in out:
            im = Image.open(os.path.join(ROOT, "images", row["path"]))
            w, h = im.size
            row["width"], row["height"] = w, h
            # 선명도: 빈 시야·초점 나간 사진을 걸러내기 위한 대략적 지표.
            # 회색조로 줄인 뒤 경계 강도의 평균을 쓴다. 값이 낮을수록 밋밋하다.
            try:
                g = im.convert("L")
                g.thumbnail((256, 256))
                px = list(g.filter(ImageFilter.FIND_EDGES).getdata())  # noqa
                row["sharpness"] = round(sum(px) / len(px), 2)
                # 교과서 선화는 흰 배경이 넓고 채도가 0에 가깝다.
                # 현미경 사진은 시야가 색으로 차 있어 흰 배경 비율이 0에 가깝다.
                c = im.convert("RGB")
                c.thumbnail((200, 200))
                cp = list(c.getdata())
                n = len(cp)
                row["white_ratio"] = round(
                    sum(1 for r, gg, b in cp if r > 238 and gg > 238 and b > 238) / n, 3)
                row["saturation"] = round(
                    sum(max(q) - min(q) for q in cp) / n, 1)
                # 흰 배경 + 거의 무채색이면 잉크 선화다. 기준을 넓히면
                # 흰 배경 위의 실물 사진(이·회충 gross)까지 걸리므로 좁게 잡는다.
                if row["white_ratio"] > 0.45 and row["saturation"] < 5:
                    row["kind"] = "drawing"
                    row["review_reason"] = "선화로 판정 (흰 배경 + 무채색)"
            except Exception:
                row["sharpness"] = None
            row.setdefault("kind", "photo")
            # **일부만 들여놓는 출처를 여기서 한 번 더 본다. 이번에는 표본으로.**
            #
            # 앞에서는 매칭된 종으로 걸렀는데, 종과 표본이 갈리는 사진이 있다 —
            # 실제실습본 p.91~92는 말라리아 단원이라 종은 난형열원충으로 잡히지만
            # 거기 실린 폐포자충 사진에는 폐포자충 표본이 붙는다. 문항에 나가는
            # 것은 **표본**이므로 그쪽이 기준이어야 한다. 종으로만 걸렀을 때
            # 원충 10장이 「말라리아만」 이라는 약속을 뚫고 나왔다.
            keep = PARTIAL.get(row.get("source"))
            if keep is not None and row["specimen_id"]:
                owner = (by_specimen_species.get(row["specimen_id"]) or "")
                if (sp_by_id.get(owner) or {}).get("group") not in keep:
                    row["kind"] = "held"
                    row["review_reason"] = (
                        f"{row['sheet']}에서는 {'·'.join(sorted(keep))}만 쓴다")
            # 표본 라벨이 불확실한 사진은 문제로 쓰지 않는다
            row["quiz_usable"] = bool(
                row["specimen_id"] and row["kind"] == "photo"
                and row["confidence"] in ("high", "medium") and min(w, h) >= 250)
    except ImportError:
        # **조용히 넘어가지 않는다.** 예전에는 여기서 기준을 낮춘 채로 계속
        # 돌았다 — 크기 검사(250px)도, 선화 판정도, **정답이 적힌 사진을
        # 빼는 것도** 건너뛰었다. 그러고도 성공한 것처럼 끝나서, 사진이
        # 606장에서 703장으로 늘어난 것을 이상하게 여기기 전까지 몰랐다.
        # 기준이 없는 결과보다 결과가 없는 편이 낫다.
        raise SystemExit(
            "Pillow 가 없습니다. 이 스크립트는 사진 크기와 선화·정답노출 판정에\n"
            "  Pillow 를 씁니다. 없이 돌리면 그 검사들이 통째로 빠집니다.\n"
            "  uv run --python 3.13 --with pillow python scripts/map_images.py")

    with open(os.path.join(DATA, "images.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"override 적용 {applied}건")

    review = [r for r in out if r["confidence"] in ("low", "none") or not r["specimen_id"]]
    with open(os.path.join(DATA, "images_unmapped.csv"), "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "source", "sheet", "row", "name_ko", "name_sub",
                    "name_en", "stage", "species_id", "specimen_id(추정)", "사유"])
        for r in review:
            w.writerow([r["path"], r["source"], r["sheet"], r["row"], r["name_ko"],
                        r["name_sub"], r["name_en"], r["stage"], r["species_id"],
                        r["specimen_id"], r["review_reason"]])

    # 표본별 커버리지 표
    per = defaultdict(lambda: Counter())
    for r in out:
        if r["specimen_id"]:
            per[r["specimen_id"]][r["section"]] += 1
            per[r["specimen_id"]]["_total"] += 1
            if r["confidence"] == "high":
                per[r["specimen_id"]]["_high"] += 1
            if r.get("quiz_usable"):
                per[r["specimen_id"]]["_usable"] += 1
    with open(os.path.join(DATA, "coverage.csv"), "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["specimen_id", "label_ko", "specimen_type", "group",
                    "이미지수", "실습사진", "강의록사진", "기타", "확정매칭", "문제사용가능"])
        for x in specimens:
            c = per.get(x["id"], Counter())
            w.writerow([x["id"], x["label_ko"], x["specimen_type"],
                        sp_by_id[x["species_id"]]["group"], c["_total"],
                        c["실습"], c["강의록"], c["기타"], c["_high"], c["_usable"]])

    final = Counter()
    for r in out:
        if r.get("kind") in ("diagram", "drawing"):
            final["모식도·선화 (제외)"] += 1
        elif r.get("kind") == "answer_visible":
            final["정답 노출 (제외)"] += 1
        elif r.get("kind") == "compare":
            final["두 종 비교 (제외)"] += 1
        elif not r["specimen_id"]:
            final["미매칭"] += 1
        elif r["confidence"] == "high":
            final["확정"] += 1
        elif r["confidence"] == "medium":
            final["유형추정"] += 1
        else:
            final["사람 확인 필요"] += 1
    print(f"이미지 {len(out)}장")
    for k, v in final.most_common():
        print(f"    {k:14s} {v:4d}")
    usable = sum(1 for r in out if r.get("quiz_usable"))
    lowres = sum(1 for r in out if r["specimen_id"] and r.get("kind") == "photo"
                 and not r.get("quiz_usable"))
    print(f"    {'문제 사용가능':14s} {usable:4d}  (저해상도 제외 {lowres}장)")
    print()

    covered = Counter(r["specimen_id"] for r in out if r["specimen_id"])
    print(f"─ 커버리지: 표본 {len(covered)}/{len(specimens)}건에 이미지 있음")
    missing = [x for x in specimens if x["id"] not in covered]
    if missing:
        print(f"─ 이미지 없는 표본 {len(missing)}건")
        for x in missing:
            print(f"    · {x['label_ko']} ({x['specimen_type']})")
    print()
    print("─ 이미지가 많은 표본 top 10")
    for sid, n in covered.most_common(10):
        print(f"    {n:3d}  {sid}")


if __name__ == "__main__":
    main()
