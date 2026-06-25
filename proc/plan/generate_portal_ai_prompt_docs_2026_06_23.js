#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const ROOT = '/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04';
const OUT = path.join(ROOT, 'data/portal-ai-prompts/2026-06-23');
const STAGES_DIR = path.join(OUT, 'stages');
const UPLOAD_DIR = path.join(OUT, 'upload');
const SOURCE_DIR = path.join(OUT, 'source');

const STATUS = [
  ['REGISTERED', '주문등록'],
  ['APPROVAL_REQUESTED', '팀장승인요청'],
  ['TEAM_LEAD_APPROVED', '임원승인요청'],
  ['EXECUTIVE_APPROVED', '출고승인요청'],
  ['RELEASE_APPROVED', '출고승인완료'],
  ['SHIPPED', '출하완료'],
  ['COMPLETED', '주문완료'],
  ['RELEASE_HOLD', '출고보류'],
  ['CLOSED_LOST', '주문취소'],
];

const sourceFiles = {
  workspace: 'data/portal-ai-prompts/2026-06-23/source/codeworkspace-relevance-scan.json',
  outline: 'data/portal-ai-prompts/2026-06-23/source/outline-inheritance-tree.md',
  teamsDigest: 'output/teams-business-rules/2026-06-17/evidence_digest.md',
  teamsFull: 'output/teams-business-rules/2026-06-17/teams_full_history_business_rules_2026-06-17.md',
  sopJake: 'output/teams-business-rules/2026-06-17/sop_docs/markdown/김규탁_업무규칙_SOP_2026-06-17.md',
  sopAnna: 'output/teams-business-rules/2026-06-17/sop_docs/markdown/조소연_업무규칙_SOP_2026-06-17.md',
  sopJaehoe: 'output/teams-business-rules/2026-06-17/sop_docs/markdown/정재회_업무규칙_SOP_2026-06-17.md',
  sopChaewon: 'output/teams-business-rules/2026-06-17/sop_docs/markdown/김채원_업무규칙_SOP_2026-06-17.md',
  sopMiyeon: 'output/teams-business-rules/2026-06-17/sop_docs/markdown/이미연_업무규칙_SOP_2026-06-17.md',
  aiSpec: '../../dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/proc/10_spec/fsd/spec-order-ai-validation.md',
  validationRules: '../../dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/apps/front/src/utils/validationRules.ts',
  orderValidation: '../../dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/packages/api-contract/src/schemas/order-validation.ts',
  incoterms: '../../dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/packages/api-contract/src/schemas/incoterms.ts',
  commonSchema: '../../dofing-order-app/order-web/dof-order-app/dof-order-web-3-az/packages/api-contract/src/schemas/common.ts',
  prodBefore: 'data/portal-ai-prompts/2026-06-23/source/prod-ai-prompts-before.csv',
};

const commonPass = [
  '입력 데이터가 단계 목적에 필요한 필수값을 갖추고, 주문/고객/제품/수금/배송/계약 정보 사이에 명백한 모순이 없다.',
  '주의나 불허에 해당하는 리스크가 없거나, 리스크가 있어도 공식 승인·메모·수금·계약·배송 근거가 주문 안에서 확인된다.',
  '국내/해외 구분에 맞는 세금, 결제, 배송, 인코텀즈, 회수, 시리얼, 출고 증적이 현재 단계에서 요구되는 수준까지 정리되어 있다.',
];

const commonCaution = [
  '필수 차단값은 아니지만 담당자가 확인해야 할 누락, 경미한 오기입, 근거 부족, 업무 메모 부족, 주소/연락처 품질 문제가 있다.',
  '수금·계약·재고·출고·회수·통관 리스크가 있으나, 공식 근거가 일부 있고 사람이 보완하면 다음 단계 진행 가능성이 있다.',
  '같은 주문 안의 제품/수금/배송/회수/첨부 정보가 완전히 맞지는 않지만 즉시 출고나 마감 금지는 아닌 경우다.',
];

const commonReject = [
  '주문 단계 전환의 핵심 필수값이 빠져 다음 단계 판단 자체가 불가능하다.',
  '주문 금액, 수량, 단가, 계약 잔액, 수금 조건, 배송/통관 조건, 시리얼/출고수량이 서로 충돌해 그대로 진행하면 잘못된 출고·회계·통관 이력이 생긴다.',
  '미수, 송금 전 출고, 전략물자, 무상/AS/반품/회수, 해외 CIPL/인코텀즈 같은 고위험 예외에 공식 승인이나 재개 조건이 없다.',
];

const commonDomestic = [
  '국내 고객사는 사업자번호, ERP ID, 계산서 이메일, 고객 연락처, 사업장/배송지 주소가 주문 단계에 맞게 갖춰져야 한다.',
  '유상 국내 주문은 수금 예정액과 주문금액이 맞아야 하며, 연체금·미수금이 큰 경우 주문 메모나 승인 근거로 출고 가능 사유가 설명되어야 한다.',
  '10만원 미만 유상 주문은 운송료 품목(SH-SH-001) 또는 운송료 무청구 사유를 확인한다.',
  '퀵/택배 요청은 주문번호, 품목, 비용 부담 주체, 픽업 가능 시간, 선불/착불 여부가 있어야 한다.',
  '소모재, Tool/Block, 소프트웨어 동글, 장비 기본 제공품은 재고·입고일·전달 대상자를 주문 메모와 제품 정보에서 확인한다.',
];

const commonOverseas = [
  '해외 주문은 국가, 통화, 과세구분, 운송방식, INCOTERMS, 배송지, 수입자/consignee 정보가 서로 맞아야 한다.',
  '외화 해외 주문은 기본적으로 수출영세가 자연스러우며, 매출과세/면세로 되어 있으면 사유 확인 대상이다.',
  'CIPL/PL은 최종 품목 확정, 포장 수량, 중량, HS code, shipping method, incoterms가 맞을 때만 신뢰한다.',
  'SH-SH-001 운송료 품목 없이 seller-paid 조건(CIP/DAP/DDP, 해상 CIF/DAP/DDP)을 쓰는 경우 무상·워런티·별도협의 등 운송료 무청구 사유를 확인한다.',
  '전략물자, 수입허가, EORI/ACID/CargoX, 최종사용자·사업장 증빙, importer 법인명 불일치, 장기 미수는 주의 또는 불허 판단의 핵심이다.',
  '일본법인/MCH/FINE LOGIC, 중국 OEM/AMJ, 중동/터키/이집트, 유럽/스페인/이탈리아, 중남미 반송·재출고처럼 반복 리스크가 있는 국가·거래처는 일반 해외 기준보다 더 엄격히 본다.',
];

const commonFieldChecks = [
  '주문명(orderName): 고객사명, 품목군, PKG/Shop/AS/무상 같은 업무 성격이 실제 주문과 맞는지 확인한다.',
  '고객사(company)와 고객(customer): 고객사가 선택되어 있고 고객 연락처가 업무상 사용할 수 있는 수준인지 본다. 국내는 사업자번호와 ERP ID를 더 엄격히 본다.',
  '국가(country): KR이면 국내 기준, KR이 아니면 해외 기준을 적용한다. 국가가 없으면 국내/해외 판정이 불가능하므로 불허에 가깝다.',
  '주문구분(orderType): 유상/무상/AS를 구분한다. 0원 제품은 무상사유가 있어야 하고, AS는 ZenDesk 또는 대상 장비·시리얼 근거가 있어야 한다.',
  '제품(products): 최소 1건, 수량 0 금지, 단가 누락 금지, 실제 품목코드와 제품명이 업무상 맞는지 확인한다.',
  '금액(totalAmount, supplyAmount, taxAmount): 제품 합계, 주문 총액, 수금 예정액이 서로 맞는지 본다. 단가/수량 반전 의심은 주의 이상이다.',
  '계약(contract): 계약/PKG 연결 주문은 계약 상태, 계약 잔액, 원주문/대체주문 관계가 맞는지 본다.',
  '수금(collections/openPaymentAmount): 유상 주문은 수금 일정이 있어야 하며, 미수·연체·송금 전 출고는 공식 승인 근거가 있어야 한다.',
  '과세구분(taxType)과 통화(currency): 국내 KRW 유상은 매출과세가 기본이고, 해외 외화 주문은 수출영세가 기본이다. 예외는 사유가 필요하다.',
  '결제조건(paymentTerms): 유상 주문은 결제조건이 있어야 하고, 기타조건은 상세 설명이 있어야 한다.',
  '배송정보(shippingAddress/phone/zipCode): 주소, 전화, 우편번호가 다음 단계에서 실제 출하 가능한 수준인지 본다. 해외 주소 특수문자와 DHL 검증 상태를 확인한다.',
  '운송방식·INCOTERMS(shippingMethod/incoterms): 해외 주문은 둘 다 필요하며, 항공/해상과 선택 가능한 조건이 맞아야 한다.',
  '운송료 품목(SH-SH-001): 운송료를 청구해야 하는 조건인데 품목이 없으면 무상·워런티·별도협의 사유를 확인한다.',
  '시리얼(serialNumbers): 시리얼 필수 제품은 수량만큼 시리얼이 있어야 주문완료 판단이 가능하다.',
  '외주/공장(factory/shippedQuantity): ROB, AMJ, DOF, 외주사 출고 기준이 다르면 실제 출고 가능일과 완료 수량을 분리해 본다.',
  '회수(recoveries): 회수조건부 출고, AS 회수, 반송은 접수와 완료를 구분한다. 회수 완료 전에는 재고/회계 마감으로 보지 않는다.',
  '첨부/문서(attachments): 전략물자, CIPL/PL, 사업자등록증, 수출허가, 송금증빙 등 단계별 증빙자료가 필요한지 본다.',
  '채터/메모/할일: 담당자 기억이나 구두 승인만으로 예외를 인정하지 않는다. 추적 가능한 공식 기록이 있어야 한다.',
];

const stageData = {
  REGISTERED: {
    goal: '주문이 다음 승인요청으로 넘어갈 수 있는 기본 입력·고객·제품·금액 구조를 갖췄는지 검증한다.',
    focus: ['주문명, 고객사, 고객, 국가, ERP ID, 사업자번호', '주문제품 최소 1건, 수량 0 금지, 단가/무상사유', '계약 연결과 계약 잔액, 주문금액과 수금 예정액', '국내/해외 구분에 따른 배송·결제·세금 기본값'],
    domestic: ['신규 고객사는 사업자등록증 기반 고객사명, 사업자번호, 계산서 이메일, 담당자 연락처, 사업장 주소가 있어야 한다.', 'ERP ID가 없으면 승인 흐름이 막히므로 고객사 채터/메모에 ERP 등록 요청 근거가 있어야 한다.', '장비 주문은 계약 제품에서 장비와 소모재를 분리하고 공장/창고(ROB, AMJ, DOF)를 확인한다.', '소모재 주문은 기존 완료 주문 복사 시 출고일, 운송장, 회계마감일 같은 과거 실행값이 따라오지 않았는지 본다.'],
    overseas: ['국가, 통화, 과세구분, 운송방식, INCOTERMS가 초기에 맞아야 뒤 단계 CIPL/PL 오류를 줄일 수 있다.', '일본 주문은 EXW/DAP, 법인가/엔드유저가, SH-SH-001 운송료 품목 여부를 초기에 분리한다.', '중국 OEM/AMJ 장비는 PO, 로트, 전압, 기본 제공품, 시리얼/라벨 확인 전 판매 주문으로 확정하지 않는다.', '전략물자 가능 품목은 최종사용자와 사용목적이 비어 있으면 최소 주의, 승인요청 전이면 불허다.'],
    caution: ['고객 연락처나 이메일은 있으나 형식·역할이 불명확하다.', '계약 잔액 초과, 수금 예정액 불일치, 10만원 미만 운송료 누락처럼 보완이 필요한 경고가 있다.', '무상/AS 사유가 짧거나 내부 메모가 부족하지만 대상 장비·원주문은 일부 확인된다.'],
    reject: ['고객사·국가·제품이 없거나 제품 수량이 0이라 주문 구조가 성립하지 않는다.', '유상 주문인데 단가/수량/총액/수금 일정이 서로 맞지 않아 금액 기준을 알 수 없다.', '국내 고객사 ERP ID 또는 해외 운송조건이 전혀 없어 다음 승인 요청이 불가능하다.'],
  },
  APPROVAL_REQUESTED: {
    goal: '팀장이 승인할 수 있도록 영업담당, 출고요청일, 결제·수금, 배송, 제품 근거가 충분한지 검증한다.',
    focus: ['영업 실적담당자, 출고요청일, 전자계산서 주소', '결제조건, 기타 결제조건 상세, 수금 일정', '배송 주소/전화/우편번호/DHL 주소 검증', 'A/S ZenDesk 티켓, 무상사유, 제품 단가/수량'],
    domestic: ['국내는 사업자번호/ERP ID와 계산서 이메일이 팀장 승인 전에 확인되어야 한다.', '미수·연체가 있는 업체는 영업담당자의 수금 독려, 입금 예정, 예외 승인 사유가 주문 메모에 있어야 한다.', '온라인샵 주문은 결제/취소 상태와 내부 주문 진행 상태가 충돌하지 않는지 본다.', '퀵 요청은 일반 택배보다 비용 부담과 긴급 사유를 더 명확히 남겨야 한다.'],
    overseas: ['해외는 INCOTERMS가 필수이며 운송방식과 선택 가능한 조건이 맞아야 한다.', 'DHL 주소가 검증되지 않았거나 특수문자/비ASCII 문자가 포함되면 주의 이상으로 본다.', 'Proforma/Draft CI는 가능하지만 PL은 포장 완료 전 신뢰할 수 없으므로 품목 확정 전 PL 근거만으로 승인하지 않는다.', '송금 전/후불/NET 조건 주문은 입금증빙 또는 공식 승인 근거가 있어야 한다.'],
    caution: ['배송 주소가 입력됐지만 DHL 검증이 없거나 일부 특수문자 문제가 있다.', '수금 일정은 있으나 주문금액과 수금 예정액이 약간 다르거나 메모가 부족하다.', '해외 무상/보증/샘플 주문의 value·incoterms·회수 여부가 일부만 정리되어 있다.'],
    reject: ['영업담당자, 출고요청일, 결제조건, 수금 일정, 배송 주소/전화가 비어 있어 팀장 승인 근거가 없다.', 'A/S 주문인데 ZenDesk 티켓 또는 대상 장비·시리얼이 없다.', '해외 주문인데 INCOTERMS/운송방식이 없거나 운송방식에 맞지 않는 조건을 고른 상태다.'],
  },
  TEAM_LEAD_APPROVED: {
    goal: '임원 승인 전에 고액·무상·계약·미수·해외 컴플라이언스 리스크가 의사결정 가능한 수준인지 검증한다.',
    focus: ['총액, 통화, 과세구분, 계약/견적 연결', 'PKG/계약 잔액 초과, 프로모션/할인 근거', '미수·연체·송금 전 출고 예외', '전략물자, 해외 수입자/최종사용자, 무상/AS 정책'],
    domestic: ['계약/PKG 주문은 원계약, 계약금액, 잔액, 차감 방식이 주문금액과 맞아야 한다.', '연체금 100만원 이상 또는 고액 미수 업체는 영업 회신만으로 충분하지 않고 수금 일정·승인 사유를 남겨야 한다.', '단가/수량 반전, 제품분류/주문명 오류는 임원 승인 전에 반려 또는 재작성해야 한다.', '중고 재출고, 데모 회수 후 판매, 무상 PKG 같은 예외는 회계/재고 처리 기준이 있어야 한다.'],
    overseas: ['외화 주문은 수출영세, 통화, payment terms, incoterms, CIPL value의 관계를 확인한다.', '전략물자·수입허가·EORI·최종사용자·사업장 증빙이 필요한 경우 자료가 없으면 임원 승인 근거가 부족하다.', '일본/해외법인 주문은 법인가, 엔드유저가, EXW/DAP, 법인 미수 상태를 분리한다.', '중남미 반송·재출고, 터키/이집트 문서 cutoff, 유럽 수입허가 등 국가별 특이 리스크를 메모에서 확인한다.'],
    caution: ['고액·미수·무상·해외 예외가 있으나 결재/메모/근거가 일부 존재한다.', '계약 잔액 또는 수금 근거가 맞아 보이나 주문 메모가 짧아 담당자 확인이 필요하다.', '해외 통관자료가 진행 중으로 보이나 아직 최종본인지 불명확하다.'],
    reject: ['계약 잔액을 초과했는데 PKG 추가 가입, 초과금 수금, 예외 승인 근거가 없다.', '송금 전 출고·장기 미수·후불 예외인데 공식 승인 기록이 없다.', '전략물자나 수입허가가 필요한데 최종사용자/사업장/사용목적 자료가 없다.'],
  },
  EXECUTIVE_APPROVED: {
    goal: '출고 승인 요청 단계에서 실제 출하 가능한 상태인지, 물류·수출·수금 관점의 멈춤 조건이 없는지 검증한다.',
    focus: ['출고일, 출하요청일, 출하담당, 재고/입고/패킹 상태', '시리얼 필요 제품, 외주/공장별 출고수량, 장비 기본 제공품', '운송사/배송지/퀵/택배/픽업 가능성', '해외 CIPL/PL, 포장수량/중량/HS code, 송금·미수 근거'],
    domestic: ['현재고와 입고 예정일이 불명확하면 출고 가능으로 확정하지 않는다.', '부분 선출고는 가능 품목, 보류 품목, 고객/영업 수락이 분리되어 있어야 한다.', '회수 접수와 회수 완료를 구분하고, 회수 완료 전 재고조정이나 주문취소 완료처럼 판단하지 않는다.', '택배 마감 이후 승인 건은 금일 출고가 아니라 실제 픽업 가능일 기준으로 판단한다.'],
    overseas: ['CIPL/PL은 최종 품목, 포장 수량, 중량, HS code, incoterms, 수입자 정보를 실제 화물 기준으로 확인한다.', 'AMJ/ROB/DOF 공장·창고가 다른 제품은 출고 가능일과 포장 기준을 분리한다.', '전략물자, 개선품 확인 전 보류, 수입자 연락 지연, 운임 청구 주체 미확정은 출고 보류 사유다.', '일본 EXW/DAP, 노미 포워더, SH-SH-001 운송료, 법인 미수 여부를 출고 전에 다시 본다.'],
    caution: ['출고일은 있으나 재고/패킹/시리얼/배송 메모가 충분하지 않다.', '국내 퀵·부분출고가 필요하지만 비용주체 또는 고객 확인이 짧게만 남아 있다.', '해외 CIPL은 있으나 포장 완료 전 draft이거나 수입자 정보가 일부 불명확하다.'],
    reject: ['출고일이 없거나 실제 재고/시리얼/패킹 수량이 주문과 맞지 않는다.', '미수·송금 전 출고·전략물자·수입허가·운임부담이 해결되지 않았는데 출고하려 한다.', '품목/수량/단가 오류가 발견되어 반려 또는 승인해제가 필요한데 그대로 진행하려 한다.'],
  },
  RELEASE_APPROVED: {
    goal: '출고 승인 완료 후 실제 출하 직전의 운송·송장·패킹·외주 출고 상태가 완결됐는지 검증한다.',
    focus: ['운송업체, 운송장번호, 배송 요청사항, 출고팀 전용 비고', '묶음배송, 외주사 출고 완료, 패킹 완료 수량', '시리얼번호, 회수조건부 출고, 택배/퀵 마감', '해외 최종 CIPL/PL, AWB/BL, 포워더 예약, 수입자 컨펌'],
    domestic: ['출고팀 전용 비고의 재고이동/매입중/입고일정 문구와 실제 승인 상태를 대조한다.', '운송장번호가 아직 없더라도 송장 출력 가능 여부와 택배 픽업 마감 시간을 확인한다.', '메디덴 등 직배송은 외주/공급사 송장과 내부 주문 상태가 함께 정리되어야 한다.', '회수조건부 출고는 회수정보 입력과 회수 기한/대상 주문번호가 있어야 한다.'],
    overseas: ['PL은 포장 완료 후 기준이므로 최종 패킹 전 draft만 있으면 주의 이상이다.', 'AWB/BL, CIPL, HS code, 포장 중량, 수입자명, importer/consignee가 같은 문서 기준인지 확인한다.', '노미 포워더 또는 도착지 운임 청구는 고객/해외영업 컨펌이 있어야 한다.', '수입자 연락 지연, 문서 cutoff 초과, 운임 차액 미확정은 출하 직전 불허 또는 출고보류 대상이다.'],
    caution: ['출고 승인은 되었으나 송장 출력/픽업/패킹 완료가 아직 확정되지 않았다.', '외주사 출고 완료 수량이 주문 수량과 같아 보이지 않거나 일부 품목만 확인된다.', '해외 최종 문서가 준비 중이고 수입자 컨펌이 아직 명확하지 않다.'],
    reject: ['운송장번호, 출고일, 시리얼, 외주사 출고수량 중 필수값이 누락되어 출하완료 판단이 불가능하다.', '실제 포장 수량/중량과 CIPL/PL/AWB 예약값이 다르다.', '출고보류 사유가 해소되지 않았는데 출고 승인 완료 상태만 보고 진행하려 한다.'],
  },
  SHIPPED: {
    goal: '출하완료 후 주문완료로 넘기기 전에 운송장, 실제 출하품, 시리얼, 외주 출고, 수금·회수 후속정보가 맞는지 검증한다.',
    focus: ['출하일, 운송장번호, 배송상태, 운송사 메모', '주문제품별 출하수량, 시리얼번호, 외주사 출고 완료', '수금 일정과 출하 후 입금 조건', '회수/반송/재발송/오배송 후속 처리'],
    domestic: ['운송장번호가 주문에 남아 있고 국내 배송 상태 조회가 가능한 형태인지 본다.', '택배 분실/오배송/재발송은 사고접수, 보상금, 재발송 주문, 재고조정까지 연결한다.', '가격 변경 후 출고된 주문은 명세서/수금 변경이 같이 됐는지 확인한다.', '부분출고는 보류 품목과 추가 발주/입고 예정이 주문 메모에 남아 있어야 한다.'],
    overseas: ['DHL/UPS/FedEx/AWB/BL 번호와 CIPL/PL 최종본이 같은 출하 건을 가리키는지 확인한다.', '해외법인/딜러 주문은 출하 후 30일 수금 기준, NET 조건, 연체 전환 시점을 확인한다.', '회수조건부 모듈/무상 보증 부품은 회수 일정과 수입 CIPL value가 정리되어야 한다.', '도착지 비용 청구, 창고료, 수입자 연락 지연 등 출하 후 비용 리스크는 주의로 남긴다.'],
    caution: ['운송장번호는 있으나 배송상태가 아직 집하 전이거나 외주사 송장 전달 예정이다.', '출하 완료와 수금/회수 후속 일정이 완전히 맞지는 않지만 추적 가능한 근거가 있다.', '해외 출하 후 문서/운임/창고료 이슈가 남아 있다.'],
    reject: ['운송장번호가 없거나 시리얼 필요 제품의 시리얼이 수량만큼 입력되지 않았다.', '외주사 제품 출고수량이 주문수량보다 적은데 주문완료로 넘기려 한다.', '오배송/분실/반송 진행 중인데 주문완료로 처리하려 한다.'],
  },
  COMPLETED: {
    goal: '주문완료 상태가 회계·수금·출하·회수·문서 이력상 마감 가능한지 검증한다.',
    focus: ['수금 완료/연체/예정 상태, 계산서/거래명세서', '출하 증적, 운송장, 시리얼, 회수 완료', '계약/PKG 잔액 반영, 매출/취소/반품 구분', '해외법인 미수금 정리와 통화별 합계'],
    domestic: ['수금탭, 회계전표, 주문번호 히스토리, 거래처원장이 서로 맞는지 본다.', '무상 PKG, 카드수금, 매출취소, 반품, 마이너스 주문은 완료 후 원장에 누락되기 쉽다.', '회수 완료 전 주문완료가 되어 있으면 회수상태와 재고조정 후속을 주의로 남긴다.', '계약 잔액이 주문 완료 후 올바르게 반영됐는지 확인한다.'],
    overseas: ['해외법인 미수금은 출고 +30일 후 수금 원칙에 따라 연체/예정/완료 상태를 구분한다.', '일본/미국/SEA는 거래처·담당자·통화 기준이 다르므로 통화별 합계를 섞지 않는다.', '수출서류, CIPL, AWB/BL, 회계마감일, 송금 회신 색상/상태가 주문과 맞아야 한다.', '출하 후 비용(창고료/운임차액/도착지 청구)이 남아 있으면 주문완료라도 주의다.'],
    caution: ['주문완료이나 미수/예정/연체 상태가 남아 있고 회수 또는 수금 후속 메모가 필요하다.', '거래명세서/계산서/원장과 포탈 주문금액 사이에 검토 필요한 차이가 있다.', '해외법인 통화별 정리가 불완전하거나 출하 후 비용이 미정이다.'],
    reject: ['출하 증적 없이 완료 처리되었거나 운송장/시리얼/외주 출고 완료가 없다.', '환불/반품/마이너스 주문이 필요한데 원주문 완료만 남겨 회계 이력이 틀어진다.', '수금·계산서·계약 잔액이 주문금액과 크게 충돌해 마감할 수 없다.'],
  },
  RELEASE_HOLD: {
    goal: '출고보류의 사유, 재개 조건, 책임 부서가 명확하고 보류 상태가 실제 리스크를 반영하는지 검증한다.',
    focus: ['보류 사유, 재개 조건, 담당자/부서, 공식 승인 여부', '미수/송금 전/연체, 재고 부족, 수입자/통관 문제', '품목 오류, 단가/수량 오류, 전략물자/허가 자료', '부분출고 가능성과 보류 품목 분리'],
    domestic: ['연체금·미수금이 큰 업체는 수금 일정 확인 전 출고보류가 유지되어야 한다.', '재고 부족은 부족 품목, 현재고, 입고 예정, 부분 선출고 가능 여부를 명확히 적는다.', '퀵/긴급 출고 요청이 있어도 비용주체와 승인 근거가 없으면 보류를 풀지 않는다.', '주문 오류는 보류보다 반려/승인해제/재작성 대상인지 구분한다.'],
    overseas: ['송금 전 출고, 수입자 연락 지연, 운임 부담 미확정, 전략물자 자료 미비는 보류 사유다.', 'CIPL/PL 값과 실제 포장값이 다르면 보류를 풀기 전에 문서 재발행이 필요하다.', '개선품 확인 전, 최종사용자/사업장 증빙 미확인, 수입허가 미완료는 불허에 가깝다.', '국가별 문서 cutoff, ACID/CargoX, EORI 등 절차 미비는 재개 조건으로 남긴다.'],
    caution: ['보류 사유는 있으나 재개 조건이나 담당 부서가 짧게만 남아 있다.', '미수/재고/문서 이슈가 일부 해결된 것으로 보이나 read-back 근거가 없다.', '부분출고 가능성이 있으나 고객/영업 확인이 아직 없다.'],
    reject: ['보류 사유가 해소되지 않았는데 출고 승인 또는 출하완료로 넘기려 한다.', '수금 일정, 공식 승인, 재고 입고, 통관자료 중 핵심 재개 조건이 없다.', '보류가 아니라 주문 반려/취소/재작성해야 하는 오류를 보류로만 덮고 있다.'],
  },
  CLOSED_LOST: {
    goal: '주문취소가 삭제·반려·재작성·환불·반품·마이너스 주문 중 올바른 처리인지 검증한다.',
    focus: ['취소 사유, 원주문/대체주문, 출고/전표/계약 이력', '수금 취소, 환불, 매출취소, 마이너스 주문', '회수/반송/재고조정, 온라인 주문 취소와 내부 진행 충돌', '해외 반송·재출고·CIPL/운임 후속'],
    domestic: ['출고/전표/계약 이력이 있는 주문은 단순 삭제하지 않고 정정주문, 마이너스 주문, 반품 처리로 나눈다.', '온라인 취소와 내부 발주/출고가 동시에 살아 있으면 취소 전 상태를 먼저 맞춘다.', '회수 접수만 있고 회수 완료가 없으면 주문취소 완료로 보지 않는다.', '원주문 단가와 반품 단가가 다르면 회계처리 기준이 필요하다.'],
    overseas: ['반송 후 재출고는 기존 주문의 연장이 아니라 새 주문/회계 처리 여부를 판단한다.', '수출자용/수입자용 CIPL, 반송 운임, 환불, 재출고 운임을 분리한다.', '무상 보증/초도불량/샘플 반송은 판매 취소와 다르게 문서 value와 회수 사유를 남긴다.', '해외 주문 취소 후에도 통관문서, AWB/BL, 창고료, 도착지 비용이 남아 있으면 주의다.'],
    caution: ['취소 사유는 있으나 원주문/대체주문/환불/회수 관계가 덜 정리되어 있다.', '온라인 취소와 내부 주문 상태가 맞아 보이나 발주/출고 중단 근거가 부족하다.', '해외 반송/환불/재출고의 운임 또는 문서 후속이 남아 있다.'],
    reject: ['출고·전표·계약 이력이 있는데 단순 취소/삭제로 처리하려 한다.', '이미 출하된 주문인데 회수/반품/마이너스 주문 없이 주문취소만 하려 한다.', '수금 취소/환불/계약 잔액 복구가 누락되어 회계 이력이 틀어진다.'],
  },
};

function ensureDirs() {
  fs.mkdirSync(STAGES_DIR, { recursive: true });
  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
}

function bullet(items) {
  return items.map((item) => `- ${item}`).join('\n');
}

function numbered(items) {
  return items.map((item, index) => `${index + 1}. ${item}`).join('\n');
}

function promptBody(stage, label, data) {
  return [
    `# ${label} 단계 주문 AI검증 업무규칙`,
    '',
    '## 역할',
    '너는 DOF 포탈 주문 데이터가 다음 업무 단계로 넘어가도 되는지 검증하는 내부 업무규칙 검토자다. 입력으로 제공된 주문 기본정보, 고객사/고객, 제품, 수금, 계약, 회수, 배송, 채터/할일, 관련 조회 데이터를 근거로만 판단한다.',
    '판정은 반드시 `통과`, `주의`, `불허` 중 하나다. 확실한 근거가 없는 내용을 새로 만들지 말고, 확인이 필요한 항목은 `주의` 또는 `불허` 사유로 적는다.',
    '',
    '## 단계 목적',
    data.goal,
    '',
    '## 공통 판정 기준',
    '### 통과',
    bullet(commonPass),
    '',
    '### 주의',
    bullet(commonCaution),
    '',
    '### 불허',
    bullet(commonReject),
    '',
    '## 이 단계에서 먼저 볼 항목',
    numbered(data.focus),
    '',
    '## 공통 필드별 확인표',
    bullet(commonFieldChecks),
    '',
    '## 국내 주문 기준',
    bullet([...commonDomestic, ...data.domestic]),
    '',
    '## 해외 주문 기준',
    bullet([...commonOverseas, ...data.overseas]),
    '',
    '## 이 단계의 주의기준',
    bullet(data.caution),
    '',
    '## 이 단계의 불허기준',
    bullet(data.reject),
    '',
    '## 판정 방법',
    '- 주문 상태명만 보고 통과시키지 말고, 현재 단계에서 다음 단계로 넘어가는 데 필요한 데이터가 실제로 준비되었는지 확인한다.',
    '- 국내와 해외 기준이 모두 걸리는 예외 주문은 더 엄격한 기준을 우선한다.',
    '- 수금·계약·재고·통관·회수·반품·운송비 같은 리스크는 담당자 메모가 아니라 주문 데이터와 공식 기록으로 확인한다.',
    '- 단순 오타처럼 보여도 단가, 수량, 통화, 과세구분, 계약 잔액, CIPL, 운송장, 시리얼, 회수정보에 영향을 주면 `주의` 이상이다.',
    '- 그대로 진행하면 잘못된 출고, 통관, 회계, 원장, 재고 이력이 생기는 경우는 `불허`다.',
    '- 사유 설명은 짧게 쓰되, 어떤 필드나 업무조건이 문제인지 드러나게 쓴다.',
    '',
    '## 응답 원칙',
    '- `통과`이면 주의사유설명과 불가사유설명은 null로 둔다.',
    '- `주의`이면 주의사유설명에 보완할 항목과 확인 주체를 1~2문장으로 적고, 불가사유설명은 null로 둔다.',
    '- `불허`이면 불가사유설명에 진행을 막는 핵심 사유와 재개 조건을 1~2문장으로 적는다. 주의 사유가 별도로 있으면 주의사유설명도 적을 수 있다.',
  ].join('\n');
}

function sourceDoc(stage, label, data, body) {
  return [
    `# ${label}(${stage}) 단계 AI검증 프롬프트 근거 문서`,
    '',
    '- 작성일: 2026-06-23',
    '- 대상: 포탈 본섭 `/admin/ai-prompts` ORDER 프롬프트',
    '- 업로드 본문: `../upload/' + stage + '.md`',
    '- 국내/해외 기준: 본 문서와 업로드 본문 모두 분리 섹션으로 작성',
    '',
    '## 사용 근거',
    '- `.code-workspace` 전체 폴더 관련성 스캔: `' + sourceFiles.workspace + '`',
    '- Outline 인수인계서 하위 문서: `' + sourceFiles.outline + '`',
    '- Teams 전체 수집 및 업무규칙 분석: `' + sourceFiles.teamsFull + '`, `' + sourceFiles.teamsDigest + '`',
    '- 퇴사자/담당자 업무규칙 SOP: `' + sourceFiles.sopJake + '`, `' + sourceFiles.sopAnna + '`, `' + sourceFiles.sopJaehoe + '`, `' + sourceFiles.sopChaewon + '`, `' + sourceFiles.sopMiyeon + '`',
    '- 포탈 AI검증 명세/코드: `' + sourceFiles.aiSpec + '`, `' + sourceFiles.validationRules + '`, `' + sourceFiles.orderValidation + '`, `' + sourceFiles.incoterms + '`, `' + sourceFiles.commonSchema + '`',
    '- 운영 DB 기존 프롬프트 스냅샷: `' + sourceFiles.prodBefore + '`',
    '',
    '## 근거 요약',
    '- 포탈 코드 기준 이 단계 프롬프트는 `AiValidationPrompt(entityType=ORDER, stage=' + stage + ')`의 최신 활성 버전으로 실행된다.',
    '- Teams 업무규칙 분석은 2026-06-17 기준 채팅방 114개, 채널 히스토리 32개 파일, 채널 reply 오류 0건을 기반으로 생성된 산출물을 사용했다.',
    '- Outline 인수인계서는 상위 문서 본문이 비어 있어 하위 5개 문서의 내용을 실제 원천으로 사용했다.',
    '- 업로드용 본문에는 이 출처 목록과 사람별 증거를 제거하고 일반 업무규칙만 남겼다.',
    '',
    '## 단계별 해석',
    `- 단계 목적: ${data.goal}`,
    '- 검토 초점:',
    bullet(data.focus),
    '',
    '## 국내 기준',
    bullet([...commonDomestic, ...data.domestic]),
    '',
    '## 해외 기준',
    bullet([...commonOverseas, ...data.overseas]),
    '',
    '## 주의기준',
    bullet([...commonCaution, ...data.caution]),
    '',
    '## 불허기준',
    bullet([...commonReject, ...data.reject]),
    '',
    '## 업로드용 본문',
    '',
    '```text',
    body,
    '```',
    '',
  ].join('\n');
}

function writeIndex(outputs) {
  const lines = [
    '# 포탈 AI 프롬프트 갱신 산출물',
    '',
    '- 작성일: 2026-06-23',
    '- 목적: 주문 단계별 본섭 AI검증 프롬프트를 국내/해외 기준, 주의기준, 불허기준 포함 장문 규칙으로 갱신',
    '',
    '## 디렉터리',
    '- `source/`: 수집 원천, Outline read-back, 운영 DB 변경 전 스냅샷, `.code-workspace` 관련성 스캔',
    '- `stages/`: 주문단계별 근거 포함 문서. 출처와 사람별 업무규칙 근거가 들어간다.',
    '- `upload/`: 본섭 `/admin/ai-prompts`에 올릴 출처 제거 본문. 일반 업무규칙만 들어간다.',
    '',
    '## 단계별 파일',
    '| stage | label | evidence doc | upload body | chars |',
    '|---|---|---|---:|---:|',
    ...outputs.map((row) => `| ${row.stage} | ${row.label} | ${row.stageFile} | ${row.uploadFile} | ${row.bodyLength} |`),
    '',
    '## 반영 원칙',
    '- 같은 단계의 기존 프롬프트를 덮어쓰지 않고 새 version을 생성한다.',
    '- 새 version만 `isActive=true`가 되게 하고 같은 단계의 기존 active는 `false`로 내린다.',
    '- 포탈 업로드용 본문은 출처/파일경로/사람별 증거를 포함하지 않는다.',
  ];
  fs.writeFileSync(path.join(OUT, 'index.md'), `${lines.join('\n')}\n`);
}

function main() {
  ensureDirs();
  const prompts = [];
  const outputs = [];
  STATUS.forEach(([stage, label], index) => {
    const data = stageData[stage];
    const body = promptBody(stage, label, data);
    const title = `${label} 단계 업무규칙/국내·해외 기준 AI검증`;
    const prefix = `${String(index + 1).padStart(2, '0')}_${stage}_${label}`;
    const stagePath = path.join(STAGES_DIR, `${prefix}.md`);
    const uploadPath = path.join(UPLOAD_DIR, `${stage}.md`);
    fs.writeFileSync(stagePath, `${sourceDoc(stage, label, data, body)}\n`);
    fs.writeFileSync(uploadPath, `${body}\n`);
    prompts.push({ entityType: 'ORDER', stage, title, body });
    outputs.push({
      stage,
      label,
      title,
      stageFile: path.relative(OUT, stagePath),
      uploadFile: path.relative(OUT, uploadPath),
      bodyLength: body.length,
    });
  });
  fs.writeFileSync(path.join(UPLOAD_DIR, 'prompts.json'), JSON.stringify(prompts, null, 2));
  fs.writeFileSync(path.join(UPLOAD_DIR, 'prompts-summary.json'), JSON.stringify(outputs, null, 2));
  writeIndex(outputs);
  console.log(JSON.stringify({ out: OUT, prompts: outputs }, null, 2));
}

main();
