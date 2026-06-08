# 물류 추적 대안 리서치

작성일: 2026-06-08 KST

## 배경

Teams `DOF Inc. / init-crm-renew`의 2026-06-02 thread를 확인했다.

확인된 업무 맥락:

- 국내/국외 물류 상태 조회 자동화 검토가 필요하다.
- 특송은 DHL/UPS/FedEx 운송장 번호로 각 특송사 홈페이지에서 조회 가능하다.
- 포워딩 항공 수출은 MAWB 번호로 항공사 또는 트래킹 사이트에서 확인 가능하지만, 대체로 출발지 공항 출항/도착지 공항 도착 수준의 milestone에 그친다.
- 일부 포워더(Rohlig)는 HAWB로도 추적되는 경우가 있으나, 해외 파트너가 다르면 제공되지 않을 수 있다.
- 해상 수출은 송장번호만으로 화물 진행상태를 제공하지 않는 경우가 많고, B/L의 모선명/항차로 선박 위치를 따로 보는 식이 필요할 수 있다.
- DHL 고객사 account number는 운송료 청구/계정 식별에 가까우며, 추적번호 자체가 아니다.

결론부터 말하면, 기존 전산을 통하지 않아도 물류 추적은 가능하다. 다만 하나의 서비스로 국내택배, 특송, 항공 포워딩, 해상 포워딩, 고객 account 번호까지 모두 해결되지는 않는다. 추적 가능 여부는 `어떤 식별자가 남아 있는가`와 `그 식별자를 어느 데이터 소스가 받아주는가`에 의해 결정된다.

## 포털 기록 기준 DOF 해외 배송 방식

포털 코드/문서/DB를 읽어본 결과, DOF 해외 배송은 하나의 방식이 아니라 아래 방식들이 섞여 있다.

### 1. DHL/FedEx/UPS/TNT 같은 국제특송

가장 많이 보이는 방식이다.

- 주요 carrier/문구: `DHL`, `FedEx`, `TNT`, `UPS`, `SF Express`, `EMS`, `Aramex`
- 포털 기록 형태: `carrier`에 carrier명 또는 account 문구, `trackingNumber`에 waybill/tracking number, pickup number, 예약 완료 메모가 섞여 있음
- 예시 패턴: `FEDEX 예약 완료`, `송장번호`, `DHL...`, `Pickup No`
- 추적 방식: carrier + waybill/tracking number로 특송 API 또는 multi-carrier tracking API 조회
- 주의: `DHL 962294390`, `DHL Account No. ...` 같은 값은 계정/청구 번호일 수 있으므로 tracking id로 보면 안 됨

DB keyword 기준으로는 해외 추정 주문에서 DHL, FedEx, TNT, UPS가 모두 대량으로 확인된다. 따라서 국내 택배와 별개로 국제특송은 1차 자동화 대상이다.

### 2. 항공 포워딩

포털에 실제 MAWB/HAWB가 남아 있는 항공 포워딩 기록이 있다.

- 주요 forwarder/문구: `로릭코리아`, `Yusen Logistics`, `PNL Express`, `KNP`, `카고파트너코리아`, `SMART MULTIMODAL GLOBAL LOGISTICS`, `다오로지스틱스`, `우림통상`
- 포털 기록 형태: `MAWB NO`, `HAWB NO`, flight route, flight no, ETD/ETA가 `trackingNumber` 또는 메모 필드에 자유 텍스트로 기록됨
- 예시 패턴:
  - `MAWB NO.157-...`, `HAWB NO.SMGL...`
  - `MAWB NO : 065-...`, `HAWB NO : TBA`
  - `ICN-DOH`, `DOH-IST`, `ICN-RUH` 같은 flight leg
- 추적 방식: MAWB는 항공사 cargo tracking 또는 track-trace류에서 milestone 조회, HAWB는 forwarder portal에서 조회 가능할 때만 의미 있음
- 한계: 항공사 MAWB 조회는 공항 출발/도착 중심이고, door-to-door 진행은 forwarder event가 있어야 함

따라서 항공 포워딩은 `carrier tracking number`가 아니라 `MAWB`, `HAWB`, `항공사`, `flight route`를 별도 필드로 뽑아야 한다.

### 3. 해상 포워딩

해상도 실제로 쓰고 있으며, 포털에는 선박 스케줄 중심 기록이 보인다.

- 주요 forwarder/문구: `럭키필해운`, `LUCKY PHIL-KOR LOGISTICS`, `DOAM GLOBAL SHIPPING`, `로릭코리아 해상`, `가나해운`, `GREEN GLOBE`, `OEC`
- 포털 기록 형태: HBL/B/L, vessel name, voyage, ETD/ETA, port가 자유 텍스트로 기록됨
- 예시 패턴:
  - `HBL#...`
  - `<해상스케줄> NYK ISABEL 0121S ETD BUSAN ... ETA MANILA ...`
  - `SAWASDEE PACIFIC 2304S`, `ETA PORT KELANG`
- 추적 방식: B/L/HBL, booking no, container no, vessel/voyage를 선사/포워더/visibility platform에 넣어 조회
- 한계: vessel/voyage만 있으면 배 위치는 볼 수 있지만, 우리 화물이 실제로 실렸는지는 B/L, container, forwarder milestone이 필요함

따라서 해상 포워딩은 `B/L`, `HBL`, `container no`, `vessel`, `voyage`, `ETD`, `ETA`를 별도 식별자로 추출해야 한다.

### 4. 노미/고객 지정 포워더

`노미`, `DHL 노미`, `TNT 노미`, `To be discussed...`, 고객 account 사용 등으로 보이는 건들이 있다.

- 의미: DOF가 직접 carrier를 완전히 통제하지 않고 고객 또는 고객 지정 포워더가 운송을 잡는 케이스
- 추적 방식: 포털에 번호가 남으면 조회 가능하지만, 번호가 없으면 고객/포워더가 주는 문서나 메일에서 식별자를 받아야 함
- 운영 포인트: 이 케이스는 DOF 내부 출고 완료와 실제 국제 운송 추적을 분리해서 봐야 함

### 5. 핸드캐리/직접 전달

`핸드캐리`, hand carry 계열 기록도 확인된다.

- 의미: 출장자/담당자가 직접 전달하거나 특수 상황에서 일반 carrier를 쓰지 않는 방식
- 추적 방식: 외부 API가 아니라 내부 milestone, 담당자 확인, QR scan 중심
- 운영 포인트: 자동 위치 추적보다는 `누가`, `언제`, `어디서 인수/전달했는지`를 남기는 내부 이벤트가 중요함

### 6. 해외 주문 안에 섞인 국내 이동

해외 주문의 `trackingNumber` 안에 `DOF -> AMJ`, `툴 발송`, 국내 택배 운송장 같은 기록이 섞여 있다.

- 의미: 고객에게 가는 국제 운송이 아니라, 수출 전 내부/협력사 이동일 수 있음
- 예시 carrier: 롯데, 로젠, CJ, 경동, 우체국 등
- 운영 포인트: 해외 shipment와 국내 sub-shipment를 분리해야 함. 이걸 한 줄 tracking으로 보면 “해외 배송 추적”이 왜곡됨

### 포털 DB에서 본 대략적 분포

로컬 포털 DB 기준으로 삭제되지 않은 주문 26,363건 중 해외 추정 주문은 7,648건이다. 해외 추정 기준은 국가/통화/Incoterms를 조합했다.

확인된 신호:

- 국제특송: DHL, FedEx, TNT, UPS가 가장 많이 보임
- 포워더: 로릭/로릭코리아, 노미, PNL, KNP, 럭키필해운, Yusen, Duraro, Gotto, Marksman, Gana, OEC, Green Globe 등이 확인됨
- 항공 키워드: `MAWB`, `HAWB`, `AWB`, `항공` 계열 기록이 1,000건 이상 잡힘
- 해상 키워드: `해상`, `B/L`, `HBL`, `container`, `vessel`, 선박명/항차 계열 기록이 수백 건 잡힘
- Incoterms는 오래된 데이터에서 공란이 많고, 입력된 값은 `DAP`, `EXW`, `FCA`, `DDP`가 주로 보임

정리하면, DOF 해외 배송은 `국제특송 + 항공 포워딩 + 해상 포워딩 + 고객 지정 포워더/노미 + 핸드캐리 + 국내 sub-shipment`가 섞여 있다. 추적 시스템을 만들려면 carrier 하나를 고르는 문제가 아니라, 포털의 자유 텍스트에서 운송 형태와 식별자를 분리하는 것이 먼저다.

## 판단 프레임

물류 추적을 자동화하려면 먼저 아래 식별자를 주문/출고 건에 붙여야 한다.

| 운송 형태 | 추적에 필요한 식별자 | 현실적인 데이터 소스 |
|---|---|---|
| 국내 택배 | 택배사 + 운송장번호 | 스윗트래커, Delivery Tracker, AfterShip, 17TRACK, 개별 택배사 |
| DHL/UPS/FedEx 특송 | carrier + waybill/tracking number | 개별 carrier API, AfterShip, 17TRACK, EasyPost, TrackingMore |
| 항공 포워딩 | MAWB, 경우에 따라 HAWB/forwarder ref | 항공사 cargo tracking, forwarder portal, project44/FourKites류 visibility platform |
| 해상 포워딩 | B/L, booking no, container no, vessel/voyage | 선사 portal, forwarder portal, project44/Vizion류 ocean visibility, AIS vessel tracking |
| 직접배송/퀵/수기 운송 | 내부 shipment id, 기사/담당자 milestone | QR/바코드 scan, 모바일 체크인, GPS/IoT tag |

`DHL 고객사 account no`처럼 결제/청구를 위한 번호는 추적 식별자가 아니다. 주문등록 단계에서 account number만 보이면 추적 자동화에는 쓸 수 없고, 실제 waybill/tracking number가 생성되는 순간을 잡아야 한다.

## 대안 1: 통합 배송조회 API 구독

가장 빠른 방법은 carrier별 API를 직접 붙이지 않고 multi-carrier tracking API를 구독하는 것이다.

후보:

- 국내 중심: 스윗트래커, Delivery Tracker
- 글로벌 parcel/특송 중심: AfterShip, 17TRACK, TrackingMore, EasyPost, Shippo
- 개별 carrier 직접 연동: DHL Developer, FedEx Developer, UPS Developer

장점:

- 운송장번호가 있으면 구현이 빠르다.
- webhook을 쓰면 polling 부담이 줄어든다.
- carrier detection, 표준 status mapping, 실패/배송완료 이벤트 정규화를 어느 정도 대신 해준다.
- AfterShip/17TRACK 같은 글로벌 업체는 DHL/UPS/FedEx뿐 아니라 일부 국내 carrier도 지원한다.

한계:

- `운송장번호가 없는 건`은 해결하지 못한다.
- carrier detection이 틀릴 수 있어 carrier를 알면 같이 넣는 편이 좋다.
- 포워딩 항공/해상은 지원하더라도 parcel처럼 세밀한 door-to-door 이벤트가 나오지 않을 수 있다.
- 운송장번호가 carrier 시스템에 등록되기 전에는 `not found`가 정상일 수 있다.

검토 근거:

- DHL Shipment Tracking API는 tracking data 사용 시 consent/data protection 조건을 명시한다. 즉, 무작정 제3자 데이터처럼 쓰기보다 발송자/수취인 권한을 전제로 해야 한다.
- FedEx Basic Integrated Visibility는 tracking number로 FedEx shipment의 기본 tracking 정보를 제공하고, webhook/near real-time update는 advanced visibility 쪽으로 안내한다.
- UPS Tracking API 문서는 near real-time tracking, proof of delivery, 120일 retention을 명시한다.
- EasyPost는 기존 carrier tracking number로 Tracker를 만들고, 업데이트를 webhook event로 받는 구조를 제공한다.
- AfterShip은 1000+ courier를 단일 REST API/webhook으로 추적한다고 설명한다.
- 17TRACK은 3300+ carrier, webhook push, bulk tracking, dashboard/report를 내세운다.
- 스윗트래커 문서는 국내 주요 택배사뿐 아니라 EMS/DHL/UPS/FedEx 등의 배송사 코드를 제공한다.
- Delivery Tracker는 webhook 방식과 48시간 expiration keep-alive 방식을 권장하고, polling보다 callback 기반 처리를 권장한다.

적합도:

- 국내 택배와 DHL/UPS/FedEx 특송에는 1순위.
- 포워딩 항공/해상에는 보조 수단. 포워더/선사/항공사 데이터가 더 중요하다.

## 대안 2: 포워더/해상/항공 visibility platform

항공/해상은 parcel API보다 freight visibility platform이 더 맞다.

후보:

- project44, FourKites: multimodal visibility. carrier/forwarder integration, API, ETA, exception alert를 제공하는 enterprise 계열.
- Vizion: ocean/container tracking API 계열.
- MarineTraffic/Kpler AIS, VesselFinder, Spire AIS 등: 선박 위치 자체를 보는 AIS 데이터. cargo 상태가 아니라 vessel 위치를 보는 용도다.
- 포워더 자체 portal/API: Rohlig Track & Trace 같은 직접 portal.

장점:

- B/L, booking number, container number 등으로 ocean tracking을 시작할 수 있다.
- carrier/forwarder/EDI/API/AIS/port event를 결합해 일반 선박 위치 조회보다 cargo milestone에 가깝다.
- 고가 수출, 장기 운송, 지연/예외 관리에는 parcel API보다 적합하다.

한계:

- 비용과 영업 계약이 커질 수 있다.
- forwarder/carrier가 어떤 데이터 연결을 제공하는지에 따라 품질이 갈린다.
- vessel AIS만 붙이면 `배 위치`는 알 수 있지만, `우리 화물이 실제로 그 배에 실렸는지`, `컨테이너가 터미널에서 release 되었는지`는 별도 event가 필요하다.
- 항공 MAWB는 대체로 공항 milestone 중심이라, 픽업/통관/최종배송까지 보려면 forwarder event가 필요하다.

검토 근거:

- project44 Ocean Visibility는 B/L, booking number, container id 등 최소 입력으로 tracking을 시작할 수 있다고 설명한다.
- project44는 carrier/forwarder 직접 연결, EDI, API, AIS, port event monitoring을 결합한다고 설명한다.
- Kpler/MarineTraffic 계열 AIS는 선박 위치와 port call/voyage event를 API 등으로 제공하지만, 이는 vessel intelligence이지 shipment registry 자체는 아니다.

적합도:

- 해상/항공 포워딩 자동화의 본류.
- 단, DOF가 월 물량이 크지 않으면 enterprise platform보다 `포워더 portal/API + 내부 shipment registry`가 먼저다.

## 대안 3: 내부 QR/바코드 기반 milestone 추적

기존 전산과 독립적으로 가장 싸고 통제 가능한 방법은 DOF 내부 shipment id를 만들고, 포장/출고/픽업/서류수령/운송장확정/도착확인 단계에서 QR 또는 바코드를 scan하는 것이다.

예시 workflow:

1. 포장 완료 시 내부 `shipment_id` 생성.
2. QR label 출력 후 박스/서류에 부착.
3. 담당자가 휴대폰으로 milestone scan:
   - `packed`
   - `picked_up`
   - `carrier_label_issued`
   - `mawb_hawb_received`
   - `customs_docs_sent`
   - `delivered_confirmed`
4. carrier tracking number나 MAWB/B/L이 생기는 순간 shipment record에 연결.
5. 외부 API가 안 되는 구간은 내부 milestone로 고객/영업에 설명한다.

장점:

- 운송장번호가 늦게 생기는 문제를 보완한다.
- 기존 ERP/포털을 직접 바꾸지 않고도 독립 DB/Sheet/App으로 시작 가능하다.
- 담당자 책임과 누락 구간이 명확해진다.
- 특정 carrier가 API를 제공하지 않아도 내부 상태는 남는다.

한계:

- 사람이 scan하지 않으면 데이터가 생기지 않는다.
- 물류사가 들고 간 이후의 실제 위치는 모른다.
- 담당자 adoption이 핵심이다.

적합도:

- 바로 파일럿 가능.
- 물류 추적 자동화의 `기초 ledger`로 강하게 권장한다.

## 대안 4: RFID/BLE/IoT/GPS 태그

`물류에 태그를 단다`는 방식은 크게 네 단계로 나뉜다.

| 방식 | 무엇을 알 수 있나 | 장점 | 한계 |
|---|---|---|---|
| QR/바코드 | 사람이 scan한 milestone | 가장 저렴, 바로 시작 | 실시간 위치 없음 |
| Passive RFID/UHF | reader를 통과한 시점/장소 | 창고/출고장 다량 scan에 좋음 | reader 인프라 필요, 운송 중 위치 없음 |
| BLE beacon/active tag | gateway 근처 위치, 실내 asset | 창고/반복 asset 추적에 좋음 | gateway 설치 필요, 외부 운송은 제한적 |
| GPS/LTE/IoT tracker | 운송 중 위치, 온도/충격/개봉 등 | 고가/긴급/민감 화물에 강함 | 단말/통신비, 배터리, 회수/폐기, 항공/국가별 규정 검토 필요 |

후보:

- Tive: GPS/cellular/WiFi 기반 shipment location과 temperature/light/shock alert, API 제공.
- Sensolus: 박스부터 container까지 asset tracking, indoor/outdoor, 무전원 asset 중심.
- Roambee, Samsara, OnAsset 등도 같은 계열로 비교 대상.
- GS1 EPCIS: RFID/바코드/수기 이벤트를 공급망 visibility event로 표준화하는 데이터 표준.

장점:

- carrier/forwarder가 이벤트를 안 줘도 independent signal을 얻는다.
- 고가 장비, 긴급 납품, 분실/지연 리스크가 큰 shipment에는 비용 대비 의미가 있을 수 있다.
- 온도/충격/빛 감지 등 품질 이슈까지 잡을 수 있다.

한계:

- 모든 박스에 붙이면 비용/운영이 과하다.
- GPS tracker는 회수형이면 reverse logistics가 생기고, 일회용이면 단가가 부담된다.
- 항공 운송에는 배터리/무선기기 반입 조건을 반드시 확인해야 한다.
- AirTag 같은 소비자 tracker는 비즈니스 API/권한/팀 공유/정책 측면에서 본격 물류 추적용으로 보기 어렵다. 예외적인 임시 보조수단에 가깝다.

적합도:

- 전량 도입보다 `문제 shipment만 붙이는 premium tracking option`으로 시작하는 편이 맞다.

## 대안 5: 메일/문서/OCR에서 식별자 자동 추출

기존 전산 대신 실제 물류 커뮤니케이션에서 식별자를 뽑는 방식도 가능하다.

대상:

- DHL/UPS/FedEx 발송 확인 메일
- 포워더 booking confirmation
- HAWB/MAWB PDF
- B/L draft/final PDF
- invoice/packing list
- Teams/Outlook 첨부 문서

방법:

- Outlook/Gmail에서 forwarder/carrier 발송 메일을 수집한다.
- PDF/OCR/정규식/LLM을 조합해 tracking number, MAWB, HAWB, B/L, container, vessel, voyage를 추출한다.
- 추출된 식별자를 shipment registry에 붙이고, 이후 외부 tracking API 또는 manual milestone과 연결한다.

장점:

- 주문등록 단계에서 추적번호가 없더라도, 번호가 생기는 순간을 자동으로 잡을 수 있다.
- 물류팀이 실제로 쓰는 문서 흐름과 맞는다.
- 기존 전산 변경 없이 별도 수집 계층으로 시작 가능하다.

한계:

- 문서 양식이 바뀌면 파서가 깨질 수 있다.
- 개인/공용 mailbox 권한과 개인정보/영업정보 접근권한 정리가 필요하다.
- 추출 정확도 검증이 필요하다.

적합도:

- DOF에는 강하게 권장한다. 현재 문제는 “어느 API를 쓸까”보다 “추적 가능한 번호가 언제/어디에 생기는가”가 더 근본이기 때문이다.

## 권장 구조

기존 전산을 대체하기보다, 아래처럼 독립적인 `Shipment Visibility Layer`를 하나 둔다.

```text
주문/출고 건
  -> shipment registry
      - internal shipment_id
      - customer/order/ref
      - mode: domestic_parcel | express | air_freight | ocean_freight | manual
      - carrier/forwarder
      - tracking_no / waybill_no
      - MAWB / HAWB
      - B/L / booking_no / container_no
      - vessel_name / voyage
      - DHL/UPS/FedEx account_no (billing metadata only)
      - current_status
      - status_source
      - last_checked_at
      - confidence
  -> source adapters
      - domestic/global tracking API
      - direct carrier API
      - forwarder portal/API
      - AIS/container visibility API
      - email/document extraction
      - QR/manual scan
      - IoT tracker API
  -> normalized event timeline
      - when
      - where
      - what happened
      - raw source
      - normalized status
      - confidence
```

상태값은 처음부터 복잡하게 만들지 말고 다음 정도로 시작한다.

- `registered`
- `packed`
- `picked_up`
- `label_issued`
- `in_transit`
- `export_customs`
- `departed_origin`
- `arrived_destination`
- `import_customs`
- `out_for_delivery`
- `delivered`
- `exception`
- `unknown`

## 서비스 가입만으로 가능한가

짧게 말하면, `상당 부분 가능하지만 전부 자동은 아니다`.

`project44`, `FourKites`, `Shippeo`, `GoComet` 같은 real-time transportation visibility platform은 항공, 해상, parcel/특송, 도로/rail 등 여러 mode를 한 화면/API로 묶는 방향의 서비스다. 특히 project44와 FourKites는 enterprise visibility platform에 가깝고, GoComet은 Master B/L, AWB, booking number, container number 기반의 shipment tracking을 전면에 내세운다.

하지만 이런 서비스를 가입해도 아래 조건은 남는다.

- 특송은 carrier + waybill/tracking number가 있어야 한다.
- 항공은 MAWB가 기본이고, HAWB는 forwarder가 데이터를 제공해야 의미가 있다.
- 해상은 Master B/L, booking no, container no, carrier code가 중요하다. House B/L만으로는 안 되는 서비스도 있다.
- 노미/고객 지정 포워더는 고객이나 포워더가 번호를 제공해야 한다.
- 핸드캐리/직접 전달은 외부 visibility platform보다 내부 milestone/QR scan이 맞다.
- 포털의 자유 텍스트에서 번호를 뽑는 일은 결국 DOF 쪽에서 해야 한다.

### 가입 후보군

| 후보군 | 대표 서비스 | 맞는 범위 | DOF 적합도 |
|---|---|---|---|
| Enterprise 올인원 visibility | project44, FourKites, Shippeo | 항공/해상/parcel/도로/rail 통합 | 기능은 가장 넓지만 영업 견적/도입 프로젝트 성격이 강함 |
| Mid-market 국제 shipment dashboard | GoComet | Master B/L, AWB, booking, container 기반 tracking | DOF가 먼저 데모 볼 만한 후보 |
| Parcel/특송 tracking API | 17TRACK, AfterShip, TrackingMore, Shippo, EasyPost | DHL/FedEx/UPS/TNT/SF/EMS 등 운송장 조회 | 바로 PoC하기 좋음. 항공/해상 포워딩은 별도 |
| Ocean/container API | Vizion, Terminal49 | B/L, booking no, container no, carrier code | 해상 건이 많아지면 유용. 항공/특송은 별도 |
| Forwarder portal/API | Rohlig, Yusen 등 실제 사용 포워더 | 해당 포워더가 맡은 항공/해상 건 | 비용은 낮을 수 있지만 포워더별로 흩어짐 |
| GPS/IoT tracker | Tive, Roambee 등 | 고가/긴급/온도/충격 민감 shipment | 전량 도입보다 premium lane용 |

### DOF에 현실적인 가입 순서

1. `17TRACK` 또는 `TrackingMore` 또는 `AfterShip`으로 DHL/FedEx/UPS/TNT/SF/EMS 샘플 30건을 먼저 테스트한다.
2. `GoComet` 데모를 요청해 DOF의 실제 `MAWB`, `HBL/B/L`, `container`, `vessel/voyage` 샘플을 넣어본다.
3. 해상 물량과 비용 리스크가 크면 `Vizion` 또는 `Terminal49`를 별도 검토한다.
4. 모든 mode를 하나의 대시보드/API로 묶는 것이 중요하고 예산이 있으면 `project44` 또는 `FourKites`로 enterprise demo를 본다.
5. 별도 서비스 가입 전, 포털에서 식별자 추출률을 먼저 측정한다. 추적번호/MAWB/B/L 확보율이 낮으면 어떤 서비스를 가입해도 조회 성공률이 낮다.

### 벤더에게 물어볼 질문

- DHL/FedEx/UPS/TNT/SF Express/EMS 추적을 모두 지원하는가?
- MAWB만 지원하는가, HAWB도 지원하는가?
- Master B/L과 House B/L을 각각 지원하는가?
- container no만 있어도 되는가, carrier code가 필수인가?
- vessel/voyage만 있을 때 tracking이 가능한가?
- API/webhook이 있는가?
- 과거 shipment 조회와 retention 기간은 어떻게 되는가?
- carrier가 `not found`를 반환할 때 retry 정책은 어떤가?
- 고객 지정 포워더/노미 건은 어떻게 처리하는가?
- 수동 milestone과 내부 QR scan 이벤트를 섞을 수 있는가?
- 가격은 tracked shipment 기준인가, API call 기준인가, carrier connector 기준인가?

## MAWB/HAWB/B/L이 있으면 무료 조회 가능한가

가능한 경우가 많다. 다만 `무료 웹 조회`와 `업무 시스템 자동화`는 다르다.

### MAWB

MAWB는 가장 무료 조회 가능성이 높다.

- MAWB는 보통 `123-12345678` 형식이고, 앞 3자리는 항공사 prefix다.
- 항공사 cargo tracking 페이지에서 MAWB로 조회할 수 있는 경우가 많다.
- track-trace 같은 사이트는 AWB를 입력하면 앞 3자리 prefix로 항공사를 자동 선택해 항공사 tracking으로 보낸다.
- TrackJet도 MAWB 앞 3자리로 항공사를 식별해 공식 tracking page로 연결한다고 설명한다.

단, 무료 조회 결과는 보통 `예약됨`, `출발`, `도착`, `인계` 같은 항공/공항 milestone 중심이다. 픽업, 수출통관, 최종배송까지 보려면 forwarder event가 필요하다.

### HAWB

HAWB는 케이스별이다.

- HAWB는 forwarder가 개별 shipper에게 발행하는 house number다.
- 항공사 공용 tracking은 보통 MAWB 중심이다.
- HAWB 조회는 해당 forwarder portal이 열려 있을 때 가능하다.
- 일부 forwarder/물류사 portal은 MAWB 또는 HAWB 둘 다 입력받지만, 이건 업체별 제공 범위다.

따라서 HAWB만 있고 forwarder가 불명확하면 무료 공용 조회 성공률이 낮다. DOF 포털에서는 HAWB와 함께 forwarder명, MAWB를 같이 저장해야 한다.

### B/L

B/L도 무료 조회가 가능한 경우가 많지만, `어떤 B/L이냐`가 중요하다.

- 선사/캐리어가 발행한 Master B/L 또는 booking number는 선사 홈페이지에서 무료 조회되는 경우가 많다.
- Maersk는 B/L number 또는 container number로 로그인 없이도 현재 위치, 이전 이동, 예상 스케줄을 볼 수 있다고 설명한다.
- Hapag-Lloyd도 container number를 입력해 tracing information을 받을 수 있는 페이지를 제공한다.
- container no가 있으면 선사 페이지나 container tracking 사이트에서 조회 가능성이 높아진다.

반면 House B/L은 forwarder가 발행한 번호라 선사 API/페이지에서 안 되는 경우가 많다. Terminal49도 지원 번호로 Master B/L, booking number, container number를 들고, House B/L은 unsupported로 분류한다. Vizion도 B/L tracking에서 carrier가 발행한 master bill of lading과 carrier code를 요구한다.

### 정리

| 번호 | 무료 수동 조회 | 자동화/API | 주의점 |
|---|---:|---:|---|
| MAWB | 높음 | 중간 | 항공사별 page는 가능, bulk/API는 별도 |
| HAWB | 낮음~중간 | 낮음~중간 | forwarder portal 의존 |
| Master B/L | 중간~높음 | 중간~높음 | 선사/SCAC/carrier code 필요 |
| House B/L | 낮음 | 낮음 | forwarder portal 의존 |
| Container no | 높음 | 중간~높음 | carrier code가 있으면 성공률 상승 |
| Vessel/voyage | 중간 | 낮음~중간 | 배 위치/스케줄이지 우리 화물 확정 증거는 아님 |

DOF에 필요한 결론은 이렇다. `MAWB`, `Master B/L`, `container no`가 있으면 무료 조회부터 시작해도 된다. 그러나 업무 자동화까지 하려면 무료 웹페이지를 사람이 보는 수준이 아니라, `carrier/forwarder`, `번호 종류`, `carrier code`, `조회 URL`, `조회 결과 이벤트`를 구조화해야 한다.

## 4주 파일럿 제안

### 1주차: 식별자 재고 조사

최근 shipment 30~50건을 뽑아 아래를 조사한다.

- 국내 택배: carrier + 운송장번호가 남는 비율
- DHL/UPS/FedEx: waybill/tracking number가 남는 비율
- 항공: MAWB/HAWB/forwarder ref가 남는 비율
- 해상: B/L/container/vessel/voyage가 남는 비율
- 번호가 어디에서 처음 보이는지: 주문등록, 메일, PDF, Teams, 포워더 portal, invoice

이 단계의 산출물은 “추적 가능한 번호 확보율”이다. 확보율이 낮으면 API 구독부터 해도 효과가 낮다.

### 2주차: API 2종 PoC

최소 2개를 비교한다.

- 국내: 스윗트래커 또는 Delivery Tracker
- 글로벌: AfterShip 또는 17TRACK

검증 항목:

- carrier coverage
- carrier detection 정확도
- webhook 가능 여부
- not found/invalid 처리
- event latency
- 비용
- API response를 DOF 상태값으로 mapping하기 쉬운지

### 3주차: 문서/메일 추출 PoC

Outlook/Gmail/Teams 첨부에서 MAWB/HAWB/B/L/container/vessel/voyage를 추출한다.

검증 항목:

- 문서 양식별 추출 정확도
- 수작업 대비 절감 시간
- 틀린 추출을 사람이 고치는 UI/운영 방식

### 4주차: QR/manual milestone + 고위험 shipment IoT pilot

- QR label을 5~10건에 붙여 포장/픽업/운송장확정 scan을 해본다.
- 고가/긴급/분실 리스크가 큰 1~3건에만 Tive류 GPS/LTE tracker 견적 또는 trial을 검토한다.

## 의사결정

추천 순서:

1. `shipment registry + 식별자 수집`을 먼저 만든다.
2. 국내/특송은 multi-carrier tracking API를 붙인다.
3. 항공/해상은 MAWB/HAWB/B/L/container/vessel/voyage를 문서/메일에서 추출하고, 필요 시 forwarder portal/API 또는 project44/Vizion류를 붙인다.
4. 내부 milestone은 QR scan으로 보완한다.
5. IoT/GPS tag는 전량이 아니라 고위험 shipment용 premium lane으로 pilot한다.

비추천:

- carrier web page scraping만으로 시작하는 방식. 약관/차단/레이아웃 변경/로그인 문제로 운영 안정성이 낮다.
- DHL account number, customer account number를 tracking id처럼 취급하는 방식.
- AirTag류 소비자 tag를 회사 물류 추적 표준으로 삼는 방식.

## 다음 액션

1. 최근 50건 shipment를 운송 형태별로 분류한다.
2. 각 건에 남아 있는 식별자를 inventory한다.
3. 스윗트래커/Delivery Tracker/AfterShip/17TRACK 중 2개로 sample tracking PoC를 한다.
4. 포워딩 건은 Rohlig 등 실제 사용 포워더별로 `HAWB`, `MAWB`, `B/L`, `container no` 중 무엇을 portal/API가 받는지 확인한다.
5. 내부 shipment registry 초안을 만든다. 처음에는 DB가 아니라 CSV/Sheet로 시작해도 된다.

## 참고 소스

- DHL Shipment Tracking API: https://developer.dhl.com/api-reference/shipment-tracking
- DHL Express waybill/account 설명: https://www.dhl.com/discover/en-my/logistics-advice/essential-guides/airway-bill-introduction
- FedEx Basic Integrated Visibility: https://developer.fedex.com/api/en-us/catalog/track.html
- UPS Tracking API documentation: https://github.com/UPS-API/api-documentation/blob/main/Tracking.yaml
- EasyPost Tracking Guide: https://docs.easypost.com/guides/tracking-guide
- AfterShip supported couriers: https://www.aftership.com/docs/tracking/others/supported-couriers
- 17TRACK API: https://www.17track.net/en/api
- 스윗트래커 배송추적 API 문서: https://img.sweettracker.net/smartapi_doc/smartAPI_Trace%20API_v1.2.pdf
- Delivery Tracker Tracking Webhook API: https://tracker.delivery/docs/tracking-webhook-api
- project44 Ocean Visibility: https://www.project44.com/platform/visibility/ocean/
- project44 Visibility overview: https://www.project44.com/platform/visibility/
- project44 Air Visibility: https://www.project44.com/platform/visibility/air/
- project44 Ocean Shipment Visibility developer guide: https://developers.project44.com/guides/shippers/visibility/ocean/p2p/overview
- FourKites Real-Time Visibility Platform: https://www.fourkites.com/platform/real-time-visibility/
- GoComet Online Container Tracking: https://www.gocomet.com/online-container-tracking
- Vizion API input options: https://docs.vizionapi.com/docs/input-options
- Terminal49 tracking requests: https://terminal49.mintlify.dev/docs/api-docs/getting-started/tracking-shipments-and-containers
- track-trace Air Cargo: https://www.track-trace.com/aircargo
- TrackJet MAWB tracking: https://trackjet.world/
- Maersk shipment tracking FAQ: https://www.maersk.com/support/faqs/how-to-track-shipments
- Hapag-Lloyd container tracing: https://www.hapag-lloyd.com/en/online-business/track/track-by-container-solution.html
- Tive public API devices: https://developers.tive.com/docs/devices
- Tive product overview: https://www.tive.com/
- Sensolus asset tracking: https://www.sensolus.com/
- GS1 EPCIS 2.0 standard: https://ref.gs1.org/standards/epcis/2.0.1/
- Kpler/MarineTraffic AIS product page: https://www.kpler.com/product/maritime/kplerais
