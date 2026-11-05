export type Prompt = { question: string; answers: string[]; explanation: string };
export type Bundle = {
  id: string; title: string; type: string; structure: string; role: string;
  root: Prompt; follow: Prompt; connection: string; next: string;
  sources: string; original: string; structural: string; exam: string; clinical: string; gap: string;
};
export const REVISION = 'cholinergic-first10-2026-11-03-v1';
const unverifiedExam = '이 질문 방향 자체의 직접 출제 근거는 미확인. 같은 가지의 기출을 이 질문의 중요도로 자동 승계하지 않음.';
const clinicalInference = '강의 기반 설계 추론: 작용 표적과 부위를 구분하는 데 필요. 개별 문항의 임상 중요도는 별도 검토 필요.';
export const bundles: Bundle[] = [
  {
    id: 'PILOT01', title: '수용체의 갈래', type: '분류 → 비교', structure: '뼈대', role: '방향 잡기',
    root: { question: 'Acetylcholine(ACh)은 어떤 수용체를 통해 작용하는가?', answers: ['Muscarinic(M) 수용체', 'Nicotinic(N) 수용체'], explanation: '같은 ACh라도 어떤 수용체에 작용하는지에 따라 신호 전달 방식이 달라진다. 먼저 수용체 계열을 연결한다.' },
    follow: { question: 'M 수용체와 N 수용체는 신호 전달 방식이 어떻게 다른가?', answers: ['M: G단백질 연결 수용체(GPCR)', 'N: 리간드 개폐 이온통로'], explanation: '수용체 계열을 아는 것과 각 계열의 신호 전달 방식을 아는 것은 별개의 연결이다.' },
    connection: 'ACh → M/N 수용체 → 신호 전달 방식', next: '수용체가 작용하는 부위를 연결한다.',
    sources: '강의 물리 p.5–7', original: 'D01·D03', structural: '이후 약물의 표적과 장기 반응을 연결할 출발점.', exam: unverifiedExam, clinical: clinicalInference, gap: '세부 수용체 아형은 이 묶음에서 확인하지 않음.',
  },
  {
    id: 'PILOT02', title: '작용 부위', type: '나열 → 예외 연결', structure: '뼈대', role: '분포 조망',
    root: { question: 'M 수용체와 N 수용체가 작용하는 대표적인 말초 부위를 각각 말하시오.', answers: ['M: 부교감신경 절후섬유의 작동기관', 'M: 교감신경의 콜린성 땀샘 경로', 'N: 자율신경절', 'N: 부신수질', 'N: 골격근 신경근이음부'], explanation: '빠뜨린 부위를 지도에 추가하듯 익힌다. 한 부위를 떠올렸다고 다른 부위까지 확인된 것은 아니다.' },
    follow: { question: '땀샘으로 가는 교감신경 경로는 일반적인 교감신경 절후 경로와 전달물질·수용체에서 어떻게 다른가?', answers: ['일반적 교감 절후 경로: NE–아드레날린성 수용체', '교감 콜린성 땀샘 경로: ACh–M 수용체'], explanation: '신경계 이름과 전달물질·수용체를 동일한 분류축으로 생각하지 않는다.' },
    connection: 'M/N → 작용 부위 → 교감 콜린성 예외', next: '신경근이음부에서 실제 반응까지 따라간다.',
    sources: '강의 물리 p.5–6', original: 'D02', structural: '수용체 이름을 실제 신경 경로에 배치한다.', exam: unverifiedExam, clinical: clinicalInference, gap: '나열의 항목별 확인 필요. 대표 부위 목록의 회상이며 모든 분포를 망라하지 않음.',
  },
  {
    id: 'PILOT03', title: '신경근 전달', type: '개별 연결 → 과정', structure: '가지', role: '연결 확장',
    root: { question: '골격근 신경근이음부에서 ACh는 어떤 수용체에 작용하는가?', answers: ['N 수용체'], explanation: '앞에서 본 분포를 부위에서 수용체를 찾는 방향으로 연결한다. 바로 앞에서 본 답을 쓰는 것은 독립 회상 확인과 다르다.' },
    follow: { question: '이 수용체가 활성화된 뒤 근수축까지 어떤 흐름이 이어지는가?', answers: ['이온 흐름 → 종판 탈분극', '근육 활동전위 발생 → 근수축'], explanation: '수용체에서 전기적 신호를 거쳐 근육 반응으로 이어지는 흐름이다.' },
    connection: '신경근이음부 → N 수용체 → 탈분극·활동전위 → 근수축', next: '전달 과정에 약물이 개입하는 위치를 찾는다.',
    sources: '강의 물리 p.7·14', original: 'D03', structural: '수용체 분류와 신경근 기능을 연결한다.', exam: unverifiedExam, clinical: clinicalInference, gap: '앞 질문의 노출 영향을 받는 연습. 지연 회상은 별도 필요.',
  },
  {
    id: 'PILOT04', title: '전달 과정의 개입', type: '개별 연결 → 과정', structure: '뼈대·경계', role: '개입 위치 이해',
    root: { question: 'Botulinum toxin은 콜린성 신경전달의 어느 과정에 개입하며, 그 과정을 어떻게 바꾸는가?', answers: ['신경말단의 ACh 유리를 억제한다.'], explanation: 'ACh가 수용체에 작용하려면 먼저 신경말단에서 나와야 한다. 약물은 유리 과정에도 개입할 수 있다.' },
    follow: { question: 'ACh가 유리된 이후부터 그 작용이 끝날 때까지의 기본 흐름을 설명하시오.', answers: ['유리된 ACh가 수용체에 작용한다.', 'AChE에 의해 분해되면서 작용이 끝난다.'], explanation: '유리, 수용체 작용, 분해는 서로 다른 개입 지점이다.' },
    connection: 'Botulinum toxin → ACh 유리 억제 / 유리 → 수용체 작용 → 분해', next: '콜린성 반응을 강화할 방법을 생각한다.',
    sources: '강의 물리 p.8·18', original: 'D04', structural: '효현제 중심 지도에서도 유리 단계의 연결을 놓치지 않는다.', exam: unverifiedExam, clinical: clinicalInference, gap: '합성·저장 억제 약물 전체는 이번 범위로 확대하지 않음.',
  },
  {
    id: 'PILOT05', title: '반응을 강화하는 방식', type: '분류 → 인과', structure: '뼈대', role: '방향 잡기',
    root: { question: '콜린성 반응을 강화하는 약물은 작용 방식에 따라 어떻게 나뉘는가?', answers: ['직접형: 수용체를 직접 자극한다.', '간접형: ACh 분해를 억제해 작용을 증가시킨다.'], explanation: '수용체를 직접 활성화하거나, 이미 유리된 ACh가 더 많이 작용하도록 만들 수 있다.' },
    follow: { question: '간접형 약물의 주요 표적은 무엇이며, 그 표적을 억제하면 왜 콜린성 반응이 증가하는가?', answers: ['표적: AChE', 'ACh 분해 감소 → ACh 작용 증가'], explanation: '표적 이름과 표적 억제의 결과를 따로 확인한다.' },
    connection: '반응 강화 → 직접형/간접형 → 표적·결과', next: '직접형과 간접형의 하위 분류를 각각 살펴본다.',
    sources: '강의 물리 p.8', original: 'D05', structural: '이후 두 약물 가지의 작용을 구별하는 기준.', exam: unverifiedExam, clinical: clinicalInference, gap: '개별 약물의 선택성과 용도는 아직 미확인.',
  },
  {
    id: 'PILOT06', title: '직접형의 분류', type: '분류 → 예시', structure: '가지', role: '방향 잡기·구체화',
    root: { question: '직접형 콜린수용체 흥분제는 어떤 화합물군으로 나뉘는가?', answers: ['Choline ester군', '알칼로이드군'], explanation: '작용 방식으로 나눈 직접형 안에서 이번에는 화합물군을 구분한다.' },
    follow: { question: '각 군에 속하는 약물을 하나씩 말하시오.', answers: ['Choline ester군: 예를 들어 bethanechol', '알칼로이드군: 예를 들어 pilocarpine'], explanation: '대표 예를 요구하는 질문이다. 제시된 예시만을 유일한 정답 목록으로 취급하지 않는다.' },
    connection: '직접형 → 화합물군 → 개별 약물', next: '간접형은 어떤 기준으로 나누는지 비교한다.',
    sources: '강의 물리 p.8–11', original: 'D06', structural: '약물 이름이 붙을 분류 위치를 마련한다.', exam: unverifiedExam, clinical: clinicalInference, gap: '전체 약물 목록과 각 약물의 세부 특성은 남아 있음.',
  },
  {
    id: 'PILOT07', title: '간접형의 분류', type: '분류 → 경계 판단', structure: '뼈대', role: '방향 잡기·구별',
    root: { question: 'AChE 억제제는 효소와의 결합 방식과 가역성에 따라 어떻게 분류되는가?', answers: ['비공유결합 제제', '가역성 carbamate 제제', '불가역성 유기인 제제'], explanation: '결합 방식과 효소 기능의 회복을 기준으로 나눈다. 분류 기준은 제시하되 집단 이름은 먼저 제공하지 않는다.' },
    follow: { question: 'AChE와 공유결합을 형성하면 모두 불가역적 억제인가?', answers: ['아니다. Carbamate에 의해 억제된 효소는 느린 가수분해를 통해 기능이 회복될 수 있다.'], explanation: '공유결합 여부와 가역성을 단순히 같은 뜻으로 놓지 않는다.' },
    connection: 'AChE 억제제 → 결합·가역성 → 분류 경계', next: '약물이 활용되는 질환·상태의 범위를 펼친다.',
    sources: '강의 물리 p.19·22', original: 'D07·D34–36', structural: '억제 지속성과 효소 회복을 이해하는 틀.', exam: unverifiedExam, clinical: '효소 억제와 회복을 구별하는 강의 기반 추론. 치료 조건은 후속 학습 필요.', gap: '대표 제제와 지속시간 비교는 이 묶음 밖에 남아 있음.',
  },
  {
    id: 'PILOT08', title: '활용 범위', type: '나열 → 개별 기전', structure: '뼈대', role: '초기 조망·후기 통합',
    root: { question: '콜린성 작용을 이용하는 약물이 치료나 진단에 활용되는 질환·상태를 떠오르는 만큼 말하시오.', answers: ['녹내장', '구강건조증', '장운동 저하·요정체', '기관지 과민성 평가', '중증근무력증', '알츠하이머병'], explanation: '처음에는 범위를 조망한다. 모든 항목의 암기를 다음 진입 조건으로 삼지 않는다. 각 용도에 사용하는 약물은 서로 다르며 이 목록은 시범 답 범위이다.' },
    follow: { question: '구강건조증에서 콜린성 약물의 어떤 작용을 이용하는가?', answers: ['침샘의 M 수용체 자극을 통한 침 분비 증가'], explanation: '용도가 있다는 연결에 어떤 작용을 이용하는지 붙인다. 다른 용도의 기전까지 확인된 것은 아니다.' },
    connection: '콜린성 약물 → 질환·상태 → 해당 용도의 작용', next: '같은 계열 약물의 성질이 달라지는 이유를 본다.',
    sources: '강의 물리 p.12·15–17·23·29', original: 'D08·D24–25 및 치료·진단 관련 초안', structural: '개별 용도가 붙을 전체 범위를 조망한다.', exam: '초안은 건조증·용도 대응 기출을 언급하나 이 전체 나열 방향의 직접 출제는 미확인.', clinical: '강의의 치료·진단 용도에 근거. 현재 진료 표준 또는 처치 지침을 뜻하지 않음.', gap: '최종 인정 표현과 용도별 조건 검토 필요. 6항목 전부를 맞혀야 통과하는 채점은 하지 않음.',
  },
  {
    id: 'PILOT09', title: '구조와 성질', type: '특성 나열 → 인과', structure: '가지·세부', role: '비교 틀·세부 확장',
    root: { question: 'Choline ester계 약물의 구조 차이는 어떤 약리학적 특성 차이로 연결되는가?', answers: ['M/N 수용체 작용의 선택성', 'Cholinesterase 분해 감수성과 이에 따른 작용 지속성'], explanation: '구조를 구별하는 이유를 먼저 떠올린다. 이 문항은 수용체 작용과 분해에 관한 시범 비교 범위를 다룬다.' },
    follow: { question: 'Carbamoyl 구조는 cholinesterase에 의한 분해와 어떤 관계가 있는가?', answers: ['분해에 대한 저항성을 높여 가수분해가 매우 느려지도록 한다.'], explanation: '구조 변화와 기능 차이를 연결한다.' },
    connection: '구조 차이 → 선택성·분해 → 특정 구조의 효과', next: '효소와 약물의 관계를 중독 치료에서 다시 사용한다.',
    sources: '강의 물리 p.9–10', original: 'D09·D11–12', structural: '구조 암기를 기능과 연결한다.', exam: '초안의 가지 근거: 2025 17번, 2022 39·42번 구조·특성 판별. 이번 첫 질문과 동일한 회상 방향으로 확인된 것은 아님.', clinical: '선택성과 지속성을 이해한다는 강의 기반 추론.', gap: 'β-methyl, 개별 구조 판별, BBB 관련 비교는 추가 질문이 필요.',
  },
  {
    id: 'PILOT10', title: '중독과 치료 표적', type: '나열 → 비교', structure: '가지', role: '치료 연결·통합',
    root: { question: '유기인 중독 치료에 사용하는 대표적인 약물을 말하시오.', answers: ['Atropine', 'Pralidoxime'], explanation: '먼저 중독과 치료 약물을 연결한다. 그다음 각 약물이 어디에 작용하는지 구별한다.' },
    follow: { question: 'Atropine과 pralidoxime의 작용 표적과 역할은 어떻게 다른가?', answers: ['Atropine: M 수용체 차단', 'Pralidoxime: 유기인에 의해 억제된 AChE의 재활성화'], explanation: '수용체 차단과 효소 회복은 서로 다른 표적이다. 이 묶음은 완전한 중독 처치 지침이 아니다.' },
    connection: '유기인 중독 → 치료 약물 → 수용체 차단/효소 회복', next: '중독 증상, 각 치료의 범위, 재활성화 조건으로 확장한다.',
    sources: '강의 물리 p.26–28', original: 'D45', structural: '앞에서 배운 수용체와 효소를 치료 표적으로 통합한다.', exam: '초안의 관련 근거: 합본 족보 물리 p.28–30 중독, p.29 기전 구별. 치료 약물 나열 자체의 직접 출제는 미확인.', clinical: '올해 강의의 중독 사례와 치료 표적 구별에 근거.', gap: '증상 연결 D42–44, aging 등 D46–47이 남아 있음. 이 10묶음만으로 중독 단원 완료가 아님.',
  },
];
