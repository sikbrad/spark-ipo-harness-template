#!/usr/bin/env python3
"""Build a static HTML report for DOF overseas customer prospects."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from string import Template
from typing import Any


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
BASE = ROOT / "output/dof-overseas-customer-prospects/2026-05-30/scale5000"
DATA = BASE / "data"
OUT = BASE / "dof_overseas_customer_prospects.html"

COMPLETE_JSONL = DATA / "prospects_augmented_contact_complete.jsonl"
PORTAL_INCOMPLETE_JSONL = DATA / "portal_foreign_additions_contact_incomplete.jsonl"
SUMMARY_JSON = DATA / "portal_overlay_summary.json"
MAP_POINTS_JSON = DATA / "prospect_map_points.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 12) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "Unknown") for row in rows)
    return [{"label": label, "count": count} for label, count in counts.most_common(limit)]


def normalize_row(row: dict[str, Any], index: int, complete: bool) -> dict[str, Any]:
    is_portal = row.get("source_type") == "DOF portal Company"
    return {
        "id": index,
        "name": row.get("name", ""),
        "country": row.get("country", ""),
        "segment": row.get("segment", ""),
        "source": "DOF Portal" if is_portal else "Public research",
        "email": row.get("email", ""),
        "phone": row.get("phone", ""),
        "address": row.get("address", ""),
        "website": row.get("website", ""),
        "source_url": row.get("source_url", ""),
        "selection_reason": row.get("selection_reason", ""),
        "dof_fit": row.get("dof_fit", ""),
        "orders": row.get("portal_orders_count", ""),
        "portal_company_id": row.get("portal_company_id", ""),
        "missing": row.get("portal_missing_contact_fields", []),
        "complete": complete,
    }


def metric_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("최종 연락처 완비", summary["augmentedContactCompleteRows"], "바로 영업 리스트로 쓸 수 있는 행"),
        ("기본 리서치", summary["foundProspectsOriginal"], "공개 연락처 기반 해외 후보"),
        ("포탈 해외 고객", summary["portalForeignCompanies"], "DOF 포탈의 해외 회사"),
        ("포탈 연락처 완비", summary["portalForeignAdditionsContactComplete"], "포탈 추가분 중 이메일/전화/주소 완비"),
        ("포탈 보완 필요", summary["portalForeignAdditionsContactIncomplete"], "연락처 보강이 필요한 포탈 회사"),
        ("기존 목록과 확정 매칭", summary["portalForeignCompaniesAlreadyInFoundProspects"], "엄격 기준으로 중복 확인된 건"),
    ]
    return "\n".join(
        f"""<article class="metric">
          <span>{escape(label)}</span>
          <strong>{int(value):,}</strong>
          <small>{escape(desc)}</small>
        </article>"""
        for label, value, desc in cards
    )


def json_for_script(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def main() -> int:
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    map_points = json.loads(MAP_POINTS_JSON.read_text(encoding="utf-8")) if MAP_POINTS_JSON.exists() else []
    complete_rows = [normalize_row(row, idx, True) for idx, row in enumerate(read_jsonl(COMPLETE_JSONL), 1)]
    incomplete_start = len(complete_rows) + 1
    incomplete_rows = [
        normalize_row(row, incomplete_start + idx, False)
        for idx, row in enumerate(read_jsonl(PORTAL_INCOMPLETE_JSONL))
    ]
    all_rows = complete_rows + incomplete_rows

    country_counts = top_counts(complete_rows, "country", 16)
    segment_counts = top_counts(complete_rows, "segment", 10)
    source_counts = top_counts(complete_rows, "source", 4)

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    template = Template(
        r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DOF 해외 잠재 고객사 리포트</title>
  <style>
    :root {
      --bg: #f5f7f8;
      --panel: #ffffff;
      --ink: #172026;
      --muted: #65717a;
      --line: #d8e0e5;
      --brand: #0d6b6f;
      --brand-2: #184a7a;
      --accent: #a05b1b;
      --portal: #164d8f;
      --public: #22715d;
      --warn: #9a4b13;
      --shadow: 0 10px 28px rgba(30, 43, 52, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.5;
    }
    header {
      background: linear-gradient(135deg, #123c44, #1f5f65 55%, #80602e);
      color: white;
      padding: 34px 36px 30px;
    }
    .header-inner { max-width: 1380px; margin: 0 auto; }
    .eyebrow {
      margin: 0 0 10px;
      font-size: 13px;
      letter-spacing: 0;
      color: rgba(255,255,255,0.78);
    }
    h1 {
      margin: 0;
      font-size: clamp(30px, 4vw, 52px);
      line-height: 1.08;
      letter-spacing: 0;
      max-width: 980px;
    }
    .lead {
      max-width: 930px;
      margin: 16px 0 0;
      color: rgba(255,255,255,0.88);
      font-size: 17px;
    }
    main { max-width: 1380px; margin: 0 auto; padding: 24px 24px 56px; }
    section { margin-top: 24px; }
    h2 { font-size: 21px; margin: 0 0 14px; letter-spacing: 0; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      margin-top: -48px;
    }
    .metric {
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.6);
      border-radius: 8px;
      padding: 16px;
      box-shadow: var(--shadow);
      min-height: 118px;
    }
    .metric span { display: block; color: var(--muted); font-size: 13px; }
    .metric strong { display: block; margin-top: 7px; font-size: 30px; letter-spacing: 0; }
    .metric small { display: block; margin-top: 6px; color: var(--muted); font-size: 12px; }
    .grid-3 {
      display: grid;
      grid-template-columns: 1.25fr 1fr 0.9fr;
      gap: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 4px 16px rgba(20, 31, 38, 0.04);
    }
    .bar-row {
      display: grid;
      grid-template-columns: minmax(110px, 1fr) 3fr 54px;
      gap: 10px;
      align-items: center;
      margin: 8px 0;
      font-size: 13px;
    }
    .bar-label { color: #2c3a42; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .bar-track { height: 10px; background: #e8eef1; border-radius: 999px; overflow: hidden; }
    .bar-fill { height: 100%; background: linear-gradient(90deg, var(--brand), var(--brand-2)); border-radius: 999px; }
    .bar-count { text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }
    .map-panel { padding: 0; overflow: hidden; }
    .map-head {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      padding: 18px 18px 12px;
      align-items: flex-start;
    }
    .map-head h2 { margin-bottom: 4px; }
    .map-head p { margin: 0; color: var(--muted); font-size: 13px; }
    #map {
      width: 100%;
      height: 560px;
      background: #dfe7eb;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }
    .map-summary {
      flex: 0 0 auto;
      color: var(--muted);
      font-size: 13px;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .legend {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      padding: 10px 18px 14px;
      color: var(--muted);
      font-size: 12px;
    }
    .legend span { display: inline-flex; gap: 6px; align-items: center; }
    .dot {
      width: 10px;
      height: 10px;
      display: inline-block;
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.18);
    }
    .dot.public { background: var(--public); }
    .dot.portal { background: var(--portal); }
    .dot.warn { background: var(--warn); }
    .popup-title { font-weight: 750; margin-bottom: 4px; }
    .popup-line { margin: 2px 0; color: #40515a; }
    .controls {
      display: grid;
      grid-template-columns: minmax(260px, 2fr) 180px 180px 180px 140px;
      gap: 10px;
      align-items: end;
      margin-bottom: 14px;
    }
    label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 5px; }
    input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 10px 11px;
      font-size: 14px;
      background: #fff;
      color: var(--ink);
    }
    button {
      border: 1px solid #b9c7cf;
      background: #ffffff;
      color: var(--ink);
      border-radius: 7px;
      padding: 10px 12px;
      font-weight: 650;
      cursor: pointer;
    }
    button:hover { border-color: var(--brand); color: var(--brand); }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    table { width: 100%; border-collapse: collapse; min-width: 1180px; }
    th, td {
      border-bottom: 1px solid #edf1f3;
      padding: 11px 12px;
      vertical-align: top;
      text-align: left;
      font-size: 13px;
    }
    th {
      position: sticky;
      top: 0;
      background: #f7fafb;
      color: #41515b;
      z-index: 1;
      font-size: 12px;
      white-space: nowrap;
    }
    tbody tr:hover { background: #fbfcfd; }
    .name { font-weight: 720; font-size: 14px; }
    .tag {
      display: inline-flex;
      align-items: center;
      white-space: nowrap;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
    }
    .tag.portal { color: var(--portal); background: #eaf2ff; }
    .tag.public { color: var(--public); background: #e9f7f1; }
    .tag.warn { color: var(--warn); background: #fff2e4; }
    .muted { color: var(--muted); }
    .reason {
      max-width: 360px;
      color: #33434c;
    }
    a { color: #095f87; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .pager {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    .pager-actions { display: flex; gap: 8px; }
    .files {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .file-link {
      display: block;
      padding: 12px;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--ink);
    }
    .file-link strong { display: block; font-size: 13px; }
    .file-link span { color: var(--muted); font-size: 12px; }
    footer {
      margin-top: 28px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    @media (max-width: 1120px) {
      .metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 16px; }
      .grid-3 { grid-template-columns: 1fr; }
      .controls { grid-template-columns: 1fr 1fr; }
      .files { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      header { padding: 28px 20px; }
      main { padding: 16px; }
      .metrics { grid-template-columns: 1fr; }
      .controls { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <p class="eyebrow">DOF Overseas Customer Prospects · Generated $generated_at</p>
      <h1>해외 잠재 고객사 및 포탈 해외 고객사 리포트</h1>
      <p class="lead">공개 연락처 기반 해외 후보와 DOF 포탈에 등록된 해외 고객사를 합쳐 영업 검토용으로 정리했다. 기본 테이블은 이메일, 전화, 주소가 모두 확인된 항목만 보여주며, 포탈 연락처 미완비 항목은 별도 필터에서 확인할 수 있다.</p>
    </div>
  </header>
  <main>
    <section class="metrics">
      $metric_cards
    </section>

    <section class="grid-3">
      <div class="panel">
        <h2>국가 상위 분포</h2>
        <div id="countryBars"></div>
      </div>
      <div class="panel">
        <h2>세그먼트 분포</h2>
        <div id="segmentBars"></div>
      </div>
      <div class="panel">
        <h2>출처 분포</h2>
        <div id="sourceBars"></div>
      </div>
    </section>

    <section class="panel map-panel">
      <div class="map-head">
        <div>
          <h2>지도</h2>
          <p>OSM 타일 위에 고객사 위치를 표시한다. 공개 리서치 항목은 OSM 객체 좌표, 포탈 항목은 주소에서 찾은 도시 또는 국가 기준 좌표를 사용한다.</p>
        </div>
        <div class="map-summary" id="mapSummary"></div>
      </div>
      <div id="map"></div>
      <div class="legend">
        <span><i class="dot public"></i>공개 리서치</span>
        <span><i class="dot portal"></i>포탈 고객</span>
        <span><i class="dot warn"></i>연락처 보완 필요</span>
        <span>좌표 정밀도는 마커 팝업에 표시</span>
        <span>&copy; OpenStreetMap contributors</span>
      </div>
    </section>

    <section class="panel">
      <h2>고객사 목록</h2>
      <div class="controls">
        <div>
          <label for="q">검색</label>
          <input id="q" type="search" placeholder="회사명, 국가, 이메일, 주소, 선정이유 검색">
        </div>
        <div>
          <label for="source">출처</label>
          <select id="source"></select>
        </div>
        <div>
          <label for="country">국가</label>
          <select id="country"></select>
        </div>
        <div>
          <label for="segment">세그먼트</label>
          <select id="segment"></select>
        </div>
        <div>
          <label for="status">연락처 상태</label>
          <select id="status">
            <option value="complete">완비만</option>
            <option value="all">전체</option>
            <option value="incomplete">보완 필요</option>
          </select>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width: 230px;">업체</th>
              <th>국가</th>
              <th>구분</th>
              <th>출처</th>
              <th>연락처</th>
              <th style="width: 260px;">주소</th>
              <th style="width: 380px;">선정이유 / DOF 관점</th>
              <th>근거</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      <div class="pager">
        <span id="resultText"></span>
        <div class="pager-actions">
          <button id="prev" type="button">이전</button>
          <button id="next" type="button">다음</button>
        </div>
      </div>
    </section>

    <section>
      <h2>원본 데이터 파일</h2>
      <div class="files">
        <a class="file-link" href="data/prospects_augmented_contact_complete.csv"><strong>연락처 완비 CSV</strong><span>기존 리서치 + 포탈 연락처 완비</span></a>
        <a class="file-link" href="data/prospects_augmented_with_portal.csv"><strong>전체 오버레이 CSV</strong><span>연락처 미완비 포탈 항목 포함</span></a>
        <a class="file-link" href="data/portal_foreign_additions_contact_complete.csv"><strong>포탈 추가 완비 CSV</strong><span>포탈 해외 고객 중 바로 연락 가능한 항목</span></a>
      </div>
    </section>

    <footer>
      <p>매칭 기준은 이메일 exact, 포탈 웹사이트 도메인 exact, 정규화 업체명 exact + 동일 국가 기준으로 제한했다. 공용 소셜/지도/메신저 도메인은 중복 판정에 사용하지 않았다.</p>
    </footer>
  </main>

  <script id="prospect-data" type="application/json">$rows_json</script>
  <script id="map-data" type="application/json">$map_points_json</script>
  <script id="country-counts" type="application/json">$country_counts_json</script>
  <script id="segment-counts" type="application/json">$segment_counts_json</script>
  <script id="source-counts" type="application/json">$source_counts_json</script>
  <script src="https://unpkg.com/deck.gl@8.9.36/dist.min.js"></script>
  <script>
    const rows = JSON.parse(document.getElementById('prospect-data').textContent);
    const mapPoints = JSON.parse(document.getElementById('map-data').textContent);
    const countryCounts = JSON.parse(document.getElementById('country-counts').textContent);
    const segmentCounts = JSON.parse(document.getElementById('segment-counts').textContent);
    const sourceCounts = JSON.parse(document.getElementById('source-counts').textContent);
    const pageSize = 80;
    let page = 1;

    const q = document.getElementById('q');
    const source = document.getElementById('source');
    const country = document.getElementById('country');
    const segment = document.getElementById('segment');
    const status = document.getElementById('status');
    const body = document.getElementById('rows');
    const resultText = document.getElementById('resultText');
    const mapSummary = document.getElementById('mapSummary');
    let deckgl = null;
    let mapInitialized = false;
    let viewState = { longitude: 10, latitude: 24, zoom: 1.5, minZoom: 1, maxZoom: 18, pitch: 0, bearing: 0 };

    function uniq(key) {
      return Array.from(new Set(rows.map(function(row) { return row[key] || 'Unknown'; }))).sort(function(a, b) {
        return a.localeCompare(b);
      });
    }
    function fillSelect(el, values, allLabel) {
      el.innerHTML = '<option value="">'+allLabel+'</option>' + values.map(function(v) {
        return '<option value="'+escapeHtml(v)+'">'+escapeHtml(v)+'</option>';
      }).join('');
    }
    function escapeHtml(value) {
      return String(value == null ? '' : value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }
    function link(url, label) {
      if (!url) return '<span class="muted">-</span>';
      return '<a href="'+escapeHtml(url)+'" target="_blank" rel="noreferrer">'+escapeHtml(label || '열기')+'</a>';
    }
    function renderBars(targetId, counts) {
      const target = document.getElementById(targetId);
      const max = Math.max.apply(null, counts.map(function(item) { return item.count; }).concat([1]));
      target.innerHTML = counts.map(function(item) {
        const width = Math.max(3, Math.round((item.count / max) * 100));
        return '<div class="bar-row"><div class="bar-label" title="'+escapeHtml(item.label)+'">'+escapeHtml(item.label)+'</div><div class="bar-track"><div class="bar-fill" style="width:'+width+'%"></div></div><div class="bar-count">'+item.count.toLocaleString()+'</div></div>';
      }).join('');
    }
    function rowMatches(row) {
      const needle = q.value.trim().toLowerCase();
      const sourceValue = source.value;
      const countryValue = country.value;
      const segmentValue = segment.value;
      const statusValue = status.value;
      if (sourceValue && row.source !== sourceValue) return false;
      if (countryValue && row.country !== countryValue) return false;
      if (segmentValue && row.segment !== segmentValue) return false;
      if (statusValue === 'complete' && !row.complete) return false;
      if (statusValue === 'incomplete' && row.complete) return false;
      if (!needle) return true;
      const haystack = [row.name, row.country, row.segment, row.source, row.email, row.phone, row.address, row.selection_reason, row.dof_fit].join(' ').toLowerCase();
      return haystack.includes(needle);
    }
    function filtered() {
      return rows.filter(rowMatches);
    }
    function markerColor(point) {
      if (!point.complete) return [154, 75, 19, 190];
      if (point.source === 'DOF Portal') return [22, 77, 143, 190];
      return [34, 113, 93, 185];
    }
    function tooltipHtml(point) {
      const precision = [point.coordinate_precision, point.coordinate_label].filter(Boolean).join(' · ');
      const portal = point.portal_company_id ? '<div class="popup-line">Portal ID '+escapeHtml(point.portal_company_id)+(point.orders !== '' ? ' · orders '+escapeHtml(point.orders) : '')+'</div>' : '';
      return '<div class="popup-title">'+escapeHtml(point.name)+'</div>'
        + '<div class="popup-line">'+escapeHtml(point.country)+' · '+escapeHtml(point.segment)+'</div>'
        + '<div class="popup-line">'+escapeHtml(point.source)+' · '+escapeHtml(precision || 'coordinate')+'</div>'
        + portal
        + '<div class="popup-line">'+escapeHtml(point.email || '-')+'</div>'
        + '<div class="popup-line">'+escapeHtml(point.phone || '-')+'</div>'
        + '<div class="popup-line">'+escapeHtml(point.address || '-')+'</div>'
        + (point.source_url ? '<div class="popup-line">'+link(point.source_url, '근거 열기')+'</div>' : '');
    }
    function initMap() {
      if (mapInitialized) return;
      mapInitialized = true;
      if (typeof deck === 'undefined') {
        document.getElementById('map').innerHTML = '<div style="padding:24px;color:#65717a;">지도 라이브러리를 불러오지 못했습니다.</div>';
        return;
      }
      deckgl = new deck.Deck({
        parent: document.getElementById('map'),
        views: [new deck.MapView({ repeat: true })],
        viewState,
        controller: true,
        onViewStateChange: function(event) {
          viewState = event.viewState;
          deckgl.setProps({ viewState });
        },
        getTooltip: function(info) {
          if (!info.object) return null;
          return {
            html: tooltipHtml(info.object),
            style: {
              backgroundColor: 'rgba(255,255,255,0.96)',
              color: '#172026',
              border: '1px solid #d8e0e5',
              borderRadius: '8px',
              boxShadow: '0 8px 24px rgba(20,31,38,0.16)',
              maxWidth: '360px'
            }
          };
        },
        layers: []
      });
    }
    function tileLayer() {
      return new deck.TileLayer({
        id: 'osm-tile-layer',
        data: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        minZoom: 0,
        maxZoom: 19,
        tileSize: 256,
        renderSubLayers: function(props) {
          const bbox = props.tile.bbox;
          return new deck.BitmapLayer(props, {
            id: props.id + '-bitmap',
            data: null,
            image: props.data,
            bounds: [bbox.west, bbox.south, bbox.east, bbox.north]
          });
        }
      });
    }
    function pointLayer(visible) {
      return new deck.ScatterplotLayer({
        id: 'prospect-points',
        data: visible,
        pickable: true,
        radiusUnits: 'pixels',
        getRadius: function(point) { return point.coordinate_precision === 'country' ? 5 : 4; },
        getPosition: function(point) { return [Number(point.lon), Number(point.lat)]; },
        getFillColor: markerColor,
        getLineColor: [255, 255, 255, 210],
        lineWidthUnits: 'pixels',
        getLineWidth: 0.75,
        updateTriggers: {
          getFillColor: [status.value, source.value]
        }
      });
    }
    function viewForPoints(points) {
      if (!points.length || points.length > 800) {
        return { longitude: 10, latitude: 24, zoom: 1.5, minZoom: 1, maxZoom: 18, pitch: 0, bearing: 0 };
      }
      let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
      points.forEach(function(point) {
        const lon = Number(point.lon);
        const lat = Number(point.lat);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
        minLon = Math.min(minLon, lon);
        maxLon = Math.max(maxLon, lon);
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
      });
      if (!Number.isFinite(minLon)) {
        return { longitude: 10, latitude: 24, zoom: 1.5, minZoom: 1, maxZoom: 18, pitch: 0, bearing: 0 };
      }
      const longitude = (minLon + maxLon) / 2;
      const latitude = (minLat + maxLat) / 2;
      const span = Math.max(maxLon - minLon, (maxLat - minLat) * 1.6, 0.02);
      const zoom = Math.max(2, Math.min(12, Math.log2(300 / span)));
      return { longitude, latitude, zoom, minZoom: 1, maxZoom: 18, pitch: 0, bearing: 0 };
    }
    function renderMap() {
      initMap();
      if (!deckgl) return;
      const visible = mapPoints.filter(rowMatches);
      mapSummary.textContent = visible.length.toLocaleString() + '개 위치 표시';
      viewState = viewForPoints(visible);
      deckgl.setProps({ viewState, layers: [tileLayer(), pointLayer(visible)] });
    }
    function render() {
      const data = filtered();
      const pages = Math.max(1, Math.ceil(data.length / pageSize));
      if (page > pages) page = pages;
      const start = (page - 1) * pageSize;
      const pageRows = data.slice(start, start + pageSize);
      body.innerHTML = pageRows.map(function(row) {
        const sourceClass = row.source === 'DOF Portal' ? 'portal' : 'public';
        const statusTag = row.complete ? '' : '<span class="tag warn">보완 필요</span>';
        const portalMeta = row.portal_company_id ? '<div class="muted">Portal ID '+escapeHtml(row.portal_company_id)+(row.orders !== '' ? ' · orders '+escapeHtml(row.orders) : '')+'</div>' : '';
        return '<tr>'
          + '<td><div class="name">'+escapeHtml(row.name)+'</div>'+portalMeta+'</td>'
          + '<td>'+escapeHtml(row.country)+'</td>'
          + '<td>'+escapeHtml(row.segment)+'</td>'
          + '<td><span class="tag '+sourceClass+'">'+escapeHtml(row.source)+'</span> '+statusTag+'</td>'
          + '<td><div>'+escapeHtml(row.email || '-')+'</div><div class="muted">'+escapeHtml(row.phone || '-')+'</div></td>'
          + '<td>'+escapeHtml(row.address || '-')+'</td>'
          + '<td class="reason"><div>'+escapeHtml(row.selection_reason || '-')+'</div><div class="muted">'+escapeHtml(row.dof_fit || '')+'</div></td>'
          + '<td>'+link(row.source_url || row.website, '근거')+'</td>'
          + '</tr>';
      }).join('');
      resultText.textContent = data.length.toLocaleString() + '건 중 ' + (data.length ? (start + 1).toLocaleString() : '0') + '-' + Math.min(start + pageSize, data.length).toLocaleString() + ' 표시 · ' + page + '/' + pages + '페이지';
      document.getElementById('prev').disabled = page <= 1;
      document.getElementById('next').disabled = page >= pages;
      renderMap();
    }
    fillSelect(source, uniq('source'), '전체 출처');
    fillSelect(country, uniq('country'), '전체 국가');
    fillSelect(segment, uniq('segment'), '전체 세그먼트');
    renderBars('countryBars', countryCounts);
    renderBars('segmentBars', segmentCounts);
    renderBars('sourceBars', sourceCounts);
    [q, source, country, segment, status].forEach(function(el) {
      el.addEventListener('input', function() { page = 1; render(); });
      el.addEventListener('change', function() { page = 1; render(); });
    });
    document.getElementById('prev').addEventListener('click', function() { page = Math.max(1, page - 1); render(); });
    document.getElementById('next').addEventListener('click', function() { page += 1; render(); });
    render();
  </script>
</body>
</html>
"""
    )
    html = template.substitute(
        generated_at=escape(generated),
        metric_cards=metric_cards(summary),
        rows_json=json_for_script(all_rows),
        map_points_json=json_for_script(map_points),
        country_counts_json=json_for_script(country_counts),
        segment_counts_json=json_for_script(segment_counts),
        source_counts_json=json_for_script(source_counts),
    )
    OUT.write_text(html, encoding="utf-8")
    print(json.dumps({"html": str(OUT), "completeRows": len(complete_rows), "incompletePortalRows": len(incomplete_rows), "allRowsInHtml": len(all_rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
