"""One-off 2026 source-page extraction. No question/answer authoring."""
from pathlib import Path
import hashlib
import json
import math
import re
import sys
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runner import ahead

HERE = Path(__file__).resolve().parent
SOURCE = Path.home() / "SynologyDrive/감염과 면역/족보/2026/감염과 면역 족보.pdf"
OUT = ROOT / "runs/_materials/감염과 면역/261101-2026-source-pdfs"
EXPECTED_SHA = "e55ba87973cd53b5cd33e95f40eb4271a398bb0ad0ddb331673462e0c2a21343"

# Observed source heading locations: page, column (0 left / 1 right), top.
# Separate question and answer sequences retain the book's actual ordering.
Q1 = [
 ("1",4,0,65),("2",4,1,479),("3",5,0,149),("4",7,0,690),
 ("5",9,1,65),("6",9,1,459),("7-8",10,1,185),("9",15,1,313),
 ("10",16,1,288),("11",18,0,65),("12",19,0,137),("13",21,0,587),
 ("14",24,0,83),("15",24,0,398),("16",25,1,656),("17",26,1,751),
 ("18",29,0,641),("19",31,0,558),("20",33,0,302),("21",34,0,671),
 ("22",36,1,191),("23",38,1,563),("24",40,1,335),("25",42,0,724),
 ("26-28",43,1,360),("29",47,0,425),("30",48,0,739),("31",49,0,661),
 ("32",52,0,83),("33",53,0,420),("34",54,0,757),("35",56,0,361),
 ("36",57,1,557),("37",60,0,403),("38",61,1,654),("39",63,0,276),
 ("40",63,1,769),("41",65,1,281),("42",67,1,426),("43",68,1,330),
 ("44",71,0,245),("45",73,0,316),("46",74,1,764),("47",77,0,335),
 ("CBL1",78,1,498),("CBL2",83,0,269),("CBL3",84,1,279),
 ("CBL4",85,1,281),("CBL5",90,1,210),("CBL6",93,0,626),
 ("LAB",93,1,283),("TBL1",94,1,193),("TBL2",99,1,773),
]
A1 = [
 ("1",102,1,374),("2",102,1,720),("3",103,0,65),("4",103,0,483),
 ("5",103,1,131),("6",103,1,229),("7-8",103,1,593),("9",104,0,367),
 ("10",104,0,730),("11",104,1,398),("12",105,0,83),("13",105,0,495),
 ("14",105,1,149),("15",105,1,393),("16",105,1,775),("17",106,0,664),
 ("18",106,1,398),("19",107,0,541),("20",107,1,265),("21",107,1,646),
 ("22",108,0,331),("23",108,0,725),("24",108,1,693),("25",109,0,349),
 ("26-28",109,0,731),("29",109,1,553),("30",110,0,198),("31",110,0,610),
 ("32",110,1,301),("33",110,1,682),("34",111,0,349),("35",111,0,761),
 ("36",111,1,415),("37",112,0,131),("38",112,0,543),("39",112,1,198),
 ("40",112,1,562),("41",113,0,283),("42",113,0,713),("43",113,1,380),
 ("44",114,0,663),("45",114,1,639),("46",115,0,265),("47",115,0,646),
 ("CBL1",115,1,301),("CBL2",115,1,718),("CBL3",116,0,349),
 ("CBL4",116,0,695),("CBL5",116,1,488),("CBL6",117,0,185),
 ("LAB",117,0,567),("TBL1",117,1,149),("TBL2",117,1,681),
]
Q2 = [
 ("49",120,0,71),("50",122,0,661),("51",124,0,215),("52",127,0,341),
 ("53",132,1,749),("54",136,0,705),("55",139,0,324),("56",141,1,144),
 ("57",144,1,396),("58",147,0,477),("59",149,1,162),("60",152,0,251),
 ("61",155,1,144),("63",157,1,715),("66",160,1,468),("64",163,1,558),
 ("65",166,1,576),("62",170,0,756),
]
A2 = [
 ("49",176,0,71),("50",176,0,615),("51",176,1,397),("52",177,0,228),
 ("53",177,1,390),("54",178,0,246),("55",178,1,90),("56",179,0,349),
 ("57",179,1,192),("58",179,1,754),("59",180,0,603),("60",180,1,433),
 ("61",181,0,403),("63",181,1,228),("66",182,0,144),("64",182,0,724),
 ("65",182,1,590),("62",183,0,469),
]
TITLES = dict(zip(
 [r[0] for r in Q1 + Q2],
 ["감염병의 병인론","감염질환에 대한 접근","감염병의 진단","감염병의 치료원칙",
 "위장관감염·피부연조직감염·요로감염·폐렴","포도알균","감염성 질환의 병리 1·2","사슬알균",
 "장내세균의 일반적 특성","장내세균: 기회감염균·장병원성균","콜레라·캄필로박터·슈도모나스","무산소성 세균",
 "심내막염·중추신경계감염","미코박테리움","코리네박테리움·노카르디아","미코플라스마·클라미디아",
 "헤모필루스·보르데텔라·나이세리아","레지오넬라·리스테리아","항생제 약리학의 기본원리","항생제 내성균의 진단과 치료",
 "렙토스피라·매독균·보렐리아","헤르페스바이러스과","리케차","파르보바이러스",
 "파라믹소·풍진·오소믹소·피코르나바이러스","간염바이러스","아데노바이러스·폭스바이러스","소아감염",
 "신종·재출현 바이러스","토가바이러스·플라비바이러스","랍도바이러스·지발바이러스","캔디다·폐포자충",
 "아스페르길루스·크립토코쿠스·털곰팡이·피부진균감염","필로바이러스·분야바이러스","파필로마바이러스·폴리오마바이러스","레트로바이러스",
 "레오·코로나·노로바이러스","방어기전손상환자의 감염","신종 감염병에 대한 대처와 전망","감염병의 자연사와 감시·관리·예방",
 "감염병의 집단발병 역학조사","감염병의 예방원칙","감염병의 예방: 환경관리","병원감염",
 "CBL 1 세균감염","CBL 2 감염성 발진","CBL 3 바이러스감염","CBL 4 인수공통·침습성 진균감염",
 "CBL 5 방어기전손상환자의 감염","CBL 6 의학미생물학: 출제 없음 안내","미생물학 실습","TBL 1 위장관·피부연조직·요로감염·폐렴","TBL 2 심내막염·중추신경계감염",
 "면역약리학","통풍 관절염","척추 관절염","류마티스 관절염","전신 홍반 루푸스","쇼그렌 증후군",
 "전신 경화증","피부근염","혈관염","알레르기질환의 병인론","알레르기 비염","기관지 천식",
 "소아 천식","두드러기·혈관부종·아나필락시스","다양한 알레르기질환","호산구성 질환","약물 알레르기","암면역"]
))
MAP = {
 "261102_01":"2","261102_02":"1","261102_03":"3","261102_05":"4","261102_06":"TBL1","261103_01":"TBL1",
 "261104_01":"6","261104_02":"7-8","261104_03":"7-8","261104_05":"7-8",
 "261105_01":"9","261105_02":"10","261105_03":"11","261105_05":"22","261105_06":"13","261105_07":"TBL2",
 "261106_01":"TBL2","261106_03":"15","261106_05":"16","261106_06":"17",
 "261109_01":"18","261109_02":"19","261109_03":"20","261109_05":"21","261109_06":"CBL1",
 "261110_01":"12","261110_02":"23","261110_03":"24","261111_01":"25","261111_02":"26-28","261111_03":"CBL2","261111_05":"LAB",
 "261112_01":"26-28","261112_02":"26-28","261112_03":"29","261112_05":"LAB","261113_01":"30","261113_02":"31","261113_03":"CBL3","261113_05":"LAB",
 "261116_01":"32","261116_02":"33","261116_03":"37","261116_05":"35","261116_06":"36","261116_07":"CBL4",
 "261117_01":"34","261117_02":"38","261117_03":"39","261118_01":"42","261118_02":"41","261118_03":"CBL5","261118_05":"40","261118_06":"CBL6",
 "261119_01":"43","261119_02":"44","261119_03":"45","261119_05":"46","261119_06":"47",
 "261123_01":"49","261123_02":"50","261123_03":"51","261123_05":"52","261123_06":"53","261123_07":"54",
 "261124_01":"55","261124_02":"56","261124_03":"57","261125_01":"58","261125_02":"59","261125_03":"60","261125_05":"61","261125_06":"62","261125_07":"62",
 "261126_01":"63","261126_02":"65","261126_03":"64","261126_05":"66","261126_06":"60","261126_07":"52",
}


def intervals(seq, end):
    assert seq == sorted(seq, key=lambda r:r[1:])
    return {r[0]:(r[1:], (seq[i+1][1:] if i+1<len(seq) else end)) for i,r in enumerate(seq)}


def snap_boundary(doc, point):
    pno,col,y=point
    blocks=[]
    for drawing in doc[pno-1].get_drawings():
        r=drawing["rect"]
        if (drawing["fill"]==(0.0,0.0,0.0) and 10<r.width<100 and 20<r.height<110
                and int(r.x0>=298)==col and abs(r.y0-y)<5):
            blocks.append(r.y0)
    return (pno,col,min(y,math.floor(min(blocks))-1) if blocks else y)


def clips(doc, start, end):
    for pno in range(start[0], end[0]+1):
        for col in [0,1]:
            if (pno,col)<tuple(start[:2]) or (pno,col)>tuple(end[:2]):
                continue
            top = start[2] if (pno,col)==tuple(start[:2]) else 60
            bottom = end[2] if (pno,col)==tuple(end[:2]) else math.floor(doc[pno-1].rect.height-20)
            if bottom-top < 14:
                continue
            width=doc[pno-1].rect.width
            rect=fitz.Rect(0 if col==0 else 298,top,298 if col==0 else width,bottom)
            yield pno,rect


def copy_page(out, source, pno, rect=None):
    out.insert_pdf(source, from_page=pno-1, to_page=pno-1)
    page=out[-1]
    typ,group=source.xref_get_key(source[pno-1].xref,"Group")
    if typ!="null":
        assert typ=="dict" and not re.search(r"\d+\s+\d+\s+R\b",group)
        out.xref_set_key(page.xref,"Group",group)
    if rect is not None:
        page.set_cropbox(rect)
    return {"source_page":pno,"clip":list(rect) if rect is not None else None}


def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED_SHA
    assert len(Q1)==len(A1)==53 and len(Q2)==len(A2)==18
    assert set(TITLES)=={r[0] for r in Q1+Q2}
    assert len(MAP)==80 and len(set(MAP.values()))==69
    if (HERE/"upload-plan.json").exists():
        raise SystemExit("Plan already exists; reuse verified artifacts.")
    OUT.mkdir(parents=True,exist_ok=False)
    source=fitz.open(SOURCE)
    def snapped(seq):
        return [(r[0],*snap_boundary(source,r[1:])) for r in seq]
    qspans={**intervals(snapped(Q1),snap_boundary(source,(102,1,374))),**intervals(snapped(Q2),snap_boundary(source,(176,0,71)))}
    aspans={**intervals(snapped(A1),(118,1,822)),**intervals(snapped(A2),(183,1,822))}
    files={}
    for key in sorted(set(MAP.values()),key=lambda k:([r[0] for r in Q1+Q2]).index(k)):
        out=fitz.open();cover=out.new_page(width=595,height=842)
        cover.insert_font(fontname="malgun",fontfile="C:/Windows/Fonts/malgun.ttf")
        cover.insert_text((48,78),"감염과 면역 · 2026년판 족보",fontname="malgun",fontsize=22)
        cover.insert_textbox(fitz.Rect(48,116,547,235),TITLES[key],fontname="malgun",fontsize=19)
        qrange=qspans[key];arange=aspans[key]
        message=(f"원본: 감염과 면역 족보.pdf (2026년판, 183쪽)\n\n"
                 f"문제 수록 지면: 원본 {qrange[0][0]}–{qrange[1][0]}쪽\n"
                 f"정답 수록 지면: 원본 {arange[0][0]}–{arange[1][0]}쪽\n\n"
                 "교수 목록 → 문제 → 정답 순서로 구성했습니다.\n"
                 "원본의 강의 구분에 따라 합본 범위가 포함될 수 있습니다.")
        cover.insert_textbox(fitz.Rect(48,260,547,650),message,fontname="malgun",fontsize=12,lineheight=1.6)
        # Subset only the newly authored cover font before source pages arrive.
        out.subset_fonts()
        pages=[{"generated":"source_guide"}];toc=[[1,"출처와 수록 범위",1],[1,"교수 목록",2]]
        prof=[2,3] if key in {r[0] for r in Q1} else [119]
        for pno in prof:
            pages.append(copy_page(out,source,pno))
        for part,span in [("문제",qrange),("정답",arange)]:
            toc.append([1,part,len(out)+1])
            for pno,rect in clips(source,*span):
                pages.append({**copy_page(out,source,pno,rect),"part":part})
        out.set_toc(toc)
        path=OUT/f"2026-{key}-족보.pdf";out.save(path,garbage=3,deflate=True);out.close()
        files[key]={"path":str(path),"title":TITLES[key],"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                    "page_sources":pages,"page_count":len(pages),"question_span":qrange,"answer_span":arange}
        print("PREPARED",key,TITLES[key],len(pages),flush=True)
    timetable=ROOT/"data/timetable/2026_본1_2학기_시간표.json"
    cells={c.key:c for c in ahead.read_cells(timetable)}
    lectures=[]
    for run_id,key in MAP.items():
        cell=cells[run_id];item=cell.as_lecture()
        payload={"subject":"감염과 면역","runId":run_id,"uid":item.uid,"date":cell.date,"slot":cell.slot,
                 "slotEnd":cell.slot,"startTime":cell.start_time,"title":" ".join(cell.body),"professors":list(cell.professors),"author":"","version":None}
        lectures.append({"run_id":run_id,"section":key,"lecture_payload":payload,"path":files[key]["path"]})
    plan={"subject":"감염과 면역","source":{"path":str(SOURCE),"sha256":EXPECTED_SHA,"pages":183},
          "files":files,"lectures":lectures,"not_applicable":[{"run_id":"261119_07","title":"형성평가와 피드백"}],
          "notices":{"261102_01":"원본의 출제 없음 안내 포함","261118_06":"CBL6 원본은 출제 없음 안내"}}
    (HERE/"upload-plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DONE",len(files),"PDFs;",len(lectures),"lecture targets")


if __name__=="__main__":
    main()
