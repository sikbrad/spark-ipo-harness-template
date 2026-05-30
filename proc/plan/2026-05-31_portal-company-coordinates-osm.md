# 포털 고객사 좌표 OSM 연동

## 목표
포털 로컬 DB의 고객사 주소를 OSM Nominatim으로 지오코딩해 고객사에 EPSG:3857 좌표를 저장하고, 고객사 상세 페이지에서 OSM 지도를 표시한다.

## 작업 항목
- [x] 포털 고객사 스키마, API 계약, 상세 페이지의 현재 주소/상세 렌더링 구조 확인
- [x] OSM/Nominatim 호출 정책 확인 후 저속/캐시형 백필 방식 설계
- [x] 고객사 DB/API 타입에 EPSG:3857 lon/lat 필드 추가
- [x] 고객사 주소 10건만 Nominatim으로 지오코딩해 로컬 DB에 반영
- [x] 고객사 상세 페이지에 OSM 지도 표시 추가
- [ ] 브라우저에서 10건 중 좌표 저장 및 지도 표출 검증
- [ ] 검증 후 전체 백필/운영 방식 정리

## 진행 메모
- Nominatim public API는 공식 정책상 앱 식별 User-Agent/Referer가 필요하고, 무거운 사용은 최대 1 req/sec 이하로 제한된다. 큰 정기/장시간 배치는 더 보수적으로 캐시와 단일 스레드를 써야 한다.
- OSM tile은 지도 위 visible attribution과 브라우저 기본 캐시/Referer 정책을 지켜야 하므로, 상세 화면은 새 지도 라이브러리 없이 OSM embed iframe으로 구현한다.
- 로컬 DB에는 좌표가 있는 고객사 10건을 확보했다. 저장값은 EPSG:3857 X/Y(`lon`, `lat`)이고, 상세 화면에서만 WGS84로 되돌려 OSM embed에 넘긴다.
