#!/usr/bin/env python3
"""Build overseas prospect cards for DOF from browser-discovered market leads."""

from __future__ import annotations

import json
import re
import textwrap
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path("/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04")
OUT_ROOT = ROOT / "output/dof-overseas-customer-prospects/2026-05-30"
CARDS_DIR = OUT_ROOT / "cards"
DATA_DIR = OUT_ROOT / "data"
INDEX_PATH = OUT_ROOT / "README.md"
SEARCH_LOG_PATH = OUT_ROOT / "playwright_search_log.md"
DATA_PATH = DATA_DIR / "prospects.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)

KEYWORDS = re.compile(
    r"dental|dentist|clinic|lab|laborator|milling|CAD|CAM|scanner|scan|"
    r"intraoral|digital|zirconia|implant|3D|printer|workflow|design|"
    r"equipment|distribution|reseller|chairside|restoration|prosthetic",
    re.I,
)

PLAYWRIGHT_SEARCH_QUERIES = [
    "dental lab digital dentistry milling center USA",
    "full service dental laboratory CAD CAM milling center Europe",
    "dental milling center intraoral scanner dental lab UK",
    "digital dental laboratory zirconia milling center Canada",
    "dental lab CAD CAM milling center Australia",
    "dental laboratory digital dentistry 3D printing milling Germany",
    "dental distributor intraoral scanner CAD CAM milling reseller",
    "dental service organization digital lab intraoral scanner",
    "dental lab group Europe digital dentistry",
    "outsourcing dental lab intraoral scans milling center",
]


@dataclass
class Prospect:
    name: str
    country: str
    region: str
    segment: str
    url: str
    priority: str
    customer_type: str
    discovery_query: str
    search_evidence: str
    buys_sells: list[str]
    dof_fit: list[str]
    why_customer: list[str]
    suggested_offer: list[str]
    next_action: str
    notes: str = ""
    fetched: dict[str, Any] = field(default_factory=dict)


PROSPECTS: list[Prospect] = [
    Prospect(
        "Digital Dental",
        "United States",
        "North America",
        "Milling center / digital dental manufacturing",
        "https://digitaldental.com/",
        "A",
        "Direct buyer / strategic benchmark",
        PLAYWRIGHT_SEARCH_QUERIES[0],
        "Search result said the company builds mills, supplies zirconia and abutments, and offers in-house milling.",
        ["milling machines", "zirconia/materials", "abutments", "outsourced milling services"],
        ["lab scanner for incoming cases", "milling workflow integration", "benchmark against in-house milling offering"],
        ["Runs high-volume CAD/CAM and in-house milling, so scan/design data throughput matters.", "Sells to labs, making it useful as a channel or competitor benchmark."],
        ["lab scanner + model/scanning workflow", "integration discussion for scan-to-mill throughput"],
        "Map product line and identify whether equipment purchasing or channel partnership team owns CAD/CAM hardware.",
    ),
    Prospect(
        "Articon",
        "United States",
        "North America",
        "Dental milling service",
        "https://articon.com/dental-milling-service/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[0],
        "Search result described a trusted dental milling center for implant bars, frameworks and restorative components.",
        ["implant bars", "frameworks", "restorative components", "CAD/CAM milling"],
        ["lab scanner for physical models", "quality control scan workflow", "CAD/CAM production integration"],
        ["Milling service centers need reliable scan intake and verification.", "Implant bars/frameworks are high-value indications where scanner accuracy matters."],
        ["high-accuracy lab scanner demo", "case intake workflow for bars/frameworks"],
        "Approach as production efficiency account, not clinic hardware buyer.",
    ),
    Prospect(
        "JB Milling Center",
        "United States",
        "North America",
        "Dental design and milling center",
        "https://jbmillingcenter.com/pages/home-1",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[0],
        "Search result said it specializes in digital dental production and serves dental labs with design and milling services.",
        ["digital dental production", "design services", "milling services"],
        ["model scanning", "digital case intake", "lab-to-lab production workflow"],
        ["Serves other labs, so faster intake/scanning can increase capacity.", "Production services create repeatable scanner ROI."],
        ["lab scanner for lab-to-lab milling center", "workflow audit around STL intake and model scanning"],
        "Find owner/operations contact and ask about scanner bottlenecks in mixed analog/digital case intake.",
    ),
    Prospect(
        "Maxidon Dental",
        "United States",
        "North America",
        "Dental lab-to-lab CAD/CAM milling center",
        "https://www.maxidondental.com/copy-of-milling-center",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[0],
        "Search result said Maxidon provides dental lab-to-lab services through an onsite digital dental milling center.",
        ["lab-to-lab services", "CAD/CAM technology", "onsite milling"],
        ["lab scanner", "CAD/CAM workflow compatibility", "case intake from partner labs"],
        ["Lab-to-lab milling centers often receive physical models and STL files.", "A DOF scanner can be positioned as throughput and compatibility equipment."],
        ["scanner demo focused on partner lab case intake"],
        "Prioritize if they appear to own their milling equipment rather than purely outsource.",
    ),
    Prospect(
        "Stomadent Dental Laboratory",
        "United States",
        "North America",
        "Dental laboratory / milling center",
        "https://stomadentlab.com/milling-center/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[0],
        "Search result identified a milling center supporting crowns, bridges and frameworks.",
        ["crowns", "bridges", "frameworks", "milling center"],
        ["model scanning", "restorative production workflow"],
        ["Crown/bridge/framework production aligns with DOF lab scanner use cases.", "A milling center likely cares about precision, turnaround and repeatability."],
        ["scanner ROI calculator for crown/bridge workflows"],
        "Qualify current scanner stack and whether they serve outside labs.",
    ),
    Prospect(
        "AmericaSmiles Network",
        "United States",
        "North America",
        "Dental lab network / milling service",
        "https://americasmiles.net/dental-milling-services/",
        "A",
        "Channel / direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[0],
        "Search result said its certified design and milling center offers milling services to hundreds of dental labs.",
        ["network milling services", "design center", "dental lab network"],
        ["network account sales", "scanner standardization", "referral channel"],
        ["Network reach can multiply adoption across labs.", "A centralized milling service has strong scan-to-production incentives."],
        ["pilot scanner workflow with one network lab", "partner program for member labs"],
        "Treat as strategic account: one relationship could open many labs.",
    ),
    Prospect(
        "Ultra Dynamics Dental Milling Center",
        "United States",
        "North America",
        "Full-service dental lab / milling center",
        "https://ultradynamicsdental.com/about",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[0],
        "Search result said the lab evolved from traditional full-service lab to dental milling center.",
        ["full-service dental lab", "milling center", "CAD/CAM production"],
        ["lab scanner upgrade", "legacy-to-digital workflow"],
        ["Traditional labs transitioning to digital are scanner replacement candidates.", "Full-service scope increases cross-indication use."],
        ["modern lab scanner upgrade package"],
        "Look for production manager or lab owner contact.",
    ),
    Prospect(
        "Argen",
        "United States",
        "North America",
        "Dental materials / digital manufacturing services",
        "https://argen.com/digital/",
        "B",
        "Strategic partner / benchmark",
        "dental digital manufacturing zirconia milling center USA",
        "Known market player in dental alloys, zirconia and digital services; included as strategic benchmark.",
        ["zirconia/materials", "digital services", "milling/manufacturing"],
        ["scanner compatibility discussions", "material and production workflow partnerships"],
        ["Large digital services provider influences lab workflows.", "May be hard to sell as direct customer but valuable as channel/benchmark."],
        ["ecosystem partnership conversation"],
        "Research regional sales/channel contacts rather than generic lab buyer.",
    ),
    Prospect(
        "National Dentex Labs (NDX)",
        "United States",
        "North America",
        "Dental laboratory network",
        "https://nationaldentex.com/",
        "A",
        "Enterprise direct buyer",
        "large dental lab network digital dentistry USA",
        "Large US lab network; likely to standardize production technology across locations.",
        ["crowns/bridges", "implants", "digital lab services", "multi-location lab operations"],
        ["enterprise scanner standardization", "multi-site lab workflow", "service/support differentiation"],
        ["Scale makes scanner standardization and replacement cycles meaningful.", "Multi-location labs value uptime, support and integration."],
        ["enterprise pilot at one lab location", "multi-site support proposal"],
        "Find procurement/operations leadership and map existing scanner brands by location.",
    ),
    Prospect(
        "Dental Services Group (DSG)",
        "United States",
        "North America",
        "Dental laboratory network",
        "https://dentalservices.net/",
        "A",
        "Enterprise direct buyer",
        "dental lab group USA digital dentistry",
        "Large dental lab group serving dentists through multiple laboratories.",
        ["dental lab services", "restorative work", "implant and digital workflows"],
        ["scanner standardization", "lab network production digitization"],
        ["Network labs regularly need scanning and CAD/CAM compatibility.", "Enterprise account could drive multiple unit sales."],
        ["multi-lab scanner evaluation"],
        "Qualify which DSG labs operate central milling or model scanning.",
    ),
    Prospect(
        "Burbank Dental Lab",
        "United States",
        "North America",
        "Full-service digital dental lab",
        "https://burbankdental.com/",
        "B",
        "Direct buyer",
        "digital dental lab CAD CAM USA",
        "Full-service dental lab with digital restorative workflows.",
        ["restorations", "implants", "digital dentistry services"],
        ["lab scanner", "case intake", "implant/restorative workflow"],
        ["Digital full-service labs are recurring users of lab scanners.", "Implant/restorative mix fits DOF scanner accuracy positioning."],
        ["lab scanner demo with implant/restorative cases"],
        "Target lab operations or digital department.",
    ),
    Prospect(
        "Keating Dental Lab",
        "United States",
        "North America",
        "Dental laboratory",
        "https://keatingdentallab.com/",
        "B",
        "Direct buyer",
        "digital dental laboratory CAD CAM USA",
        "US dental lab known for restorative and digital services.",
        ["crowns/bridges", "implants", "digital lab services"],
        ["model scanning", "CAD/CAM workflow", "quality verification"],
        ["Restorative lab production creates daily scanner demand.", "A scanner upgrade pitch can focus on accuracy and turnaround."],
        ["scanner upgrade conversation"],
        "Check if they publish accepted intraoral scanner platforms.",
    ),
    Prospect(
        "ROE Dental Laboratory",
        "United States",
        "North America",
        "Digital dental lab / implant planning",
        "https://www.roedentallab.com/",
        "A",
        "Direct buyer",
        "digital dental lab implant planning scanning USA",
        "Digital dental laboratory with implant and guided surgery workflows.",
        ["implant cases", "guided surgery", "restorative digital workflow"],
        ["high-accuracy scan workflows", "implant case verification", "model scanning"],
        ["Implant/guided surgery workflows reward precise scan data.", "High-complexity cases justify premium equipment."],
        ["implant workflow scanner demo"],
        "Target implant planning or digital workflow leadership.",
    ),
    Prospect(
        "Dandy",
        "United States",
        "North America",
        "Fully digital dental lab platform",
        "https://www.meetdandy.com/",
        "B",
        "Strategic account / competitive benchmark",
        PLAYWRIGHT_SEARCH_QUERIES[7],
        "Search result described Dandy as a fully digital dental lab integrating intraoral scanners and CAD/CAM software.",
        ["digital lab platform", "intraoral scanner workflow", "CAD/CAM services"],
        ["scanner ecosystem partnership", "competitive intelligence", "clinic-to-lab workflow"],
        ["Dandy's model depends on scanning adoption across clinics.", "Even if competitive, it indicates demand patterns for scanner-led lab workflows."],
        ["ecosystem partnership or intelligence brief"],
        "Do not pitch as ordinary lab; study whether they buy, bundle or specify scanners.",
    ),
    Prospect(
        "Digital Dental Studio & Laboratory",
        "Canada",
        "North America",
        "Full-service digital dental lab",
        "https://www.ddsl.ca/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[3],
        "Search result said the lab uses in-house digital milling machines for e.max, zirconia and non-metal restorations.",
        ["in-house milling", "e.max", "zirconia crowns", "digital dental lab"],
        ["lab scanner", "milling workflow", "scan-to-restoration quality"],
        ["In-house milling plus restorative output makes scanner ROI straightforward.", "A Canadian digital lab may be open to non-US equipment if support is strong."],
        ["lab scanner demo for zirconia/e.max production"],
        "Qualify current scanners and material indications.",
    ),
    Prospect(
        "Lightning Dental Lab",
        "Canada",
        "North America",
        "Dental milling center",
        "https://lightningdentallab.ca/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[3],
        "Search result said it is a dental milling center serving dental laboratories in Canada and the United States.",
        ["milling center", "lab-to-lab service", "Canada/US dental labs"],
        ["model scanning", "production intake", "CAD/CAM compatibility"],
        ["Lab-to-lab milling centers are strong scanner users.", "Cross-border lab service implies scale and repeat cases."],
        ["scanner for intake and QC of milling cases"],
        "Approach as capacity/turnaround improvement account.",
    ),
    Prospect(
        "Streamline Dental",
        "Canada",
        "North America",
        "Milling center for labs and dental companies",
        "https://streamlinedental.ca/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[3],
        "Search result said it is a Canadian milling center exclusively for dental laboratories and dental companies.",
        ["milling center", "dental laboratories", "dental companies"],
        ["lab scanner", "outsourcing partner workflow", "production standardization"],
        ["Exclusive lab/company focus is a strong B2B production signal.", "DOF scanner pitch can center on consistent case intake."],
        ["B2B milling-center scanner workflow"],
        "Find production lead and ask about analog model intake percentage.",
    ),
    Prospect(
        "Newdent",
        "Canada",
        "North America",
        "Dental laboratory / milling center",
        "https://newdent.ca/milling.html",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[3],
        "Search result described digital design files and milling from zirconia, lithium disilicate, PMMA and other materials.",
        ["zirconia", "lithium disilicate", "PMMA", "digital design files", "milling"],
        ["lab scanner", "material-driven CAD/CAM workflow"],
        ["Material range suggests active CAD/CAM production.", "Digital design file workflow needs reliable scan inputs."],
        ["scanner demo around multi-material milling"],
        "Qualify current model scanner and whether scanner replacement is planned.",
    ),
    Prospect(
        "Digital One Dental Technologies",
        "Canada",
        "North America",
        "Dental milling / digital outsourcing",
        "https://digitalonedental.com/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[3],
        "Search result referenced outsourcing zirconia work to Digital One.",
        ["zirconia outsourcing", "dental milling", "digital technologies"],
        ["lab scanner", "digital intake", "outsourcing workflow"],
        ["Outsourcing labs depend on accurate input files and model scans.", "Zirconia production aligns with high-throughput scanner use."],
        ["scanner package for zirconia outsourcing workflows"],
        "Target owner/production contact.",
    ),
    Prospect(
        "Modern Dental Lab Canada",
        "Canada",
        "North America",
        "Dental lab / global lab group branch",
        "https://www.moderndentalcanada.com/products/",
        "A",
        "Enterprise direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[3],
        "Search result said restorations are milled from zirconia at digital milling centers.",
        ["zirconia restorations", "digital milling centers", "dental products"],
        ["enterprise scanner standardization", "lab scanner fleet", "CAD/CAM integration"],
        ["Modern Dental is a major lab platform; equipment standardization can scale.", "Digital milling centers signal need for upstream scan workflows."],
        ["regional pilot leading to group-level discussion"],
        "Map decision path between Canada branch and Modern Dental Group procurement.",
    ),
    Prospect(
        "Emerald Dental Works",
        "Canada",
        "North America",
        "Digital dental lab support / milling",
        "http://emeralddental.com/digital-dental-labs.html",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[3],
        "Search result said they have milled over 60,000 units for digital dental labs throughout Canada.",
        ["milled units", "digital dental labs", "model work"],
        ["scanner for lab intake", "production QC", "digital lab support"],
        ["High unit volume supports equipment ROI.", "Serving digital labs suggests openness to workflow technology."],
        ["scanner workflow for high-volume unit milling"],
        "Verify current operations and contact path due older-looking site.",
    ),
    Prospect(
        "CADdent",
        "Germany",
        "Europe",
        "Dental milling / laser melting / 3D printing center",
        "https://www.caddent.de/en/milling",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[1],
        "Search result described multi-axis CAD/CAM high-tech systems in a dental milling center.",
        ["multi-axis milling", "CAD/CAM", "laser melting", "3D printing"],
        ["lab scanner", "industrialized production integration", "high-accuracy workflow"],
        ["Advanced production centers are strong scanner and QC equipment users.", "German market validates premium accuracy positioning."],
        ["scanner/QC workflow discussion for milling center"],
        "Find production technology or partner management contact.",
    ),
    Prospect(
        "New Ancorvis",
        "Italy",
        "Europe",
        "CAD/CAM dental milling center",
        "https://www.newancorvis.eu/dental-cad-cam-milling-center/",
        "A",
        "Direct buyer / channel",
        PLAYWRIGHT_SEARCH_QUERIES[1],
        "Search result described certified production workflow, technical support and sales network.",
        ["CAD/CAM milling", "production workflow", "sales network", "semi-finished products"],
        ["scanner integration", "channel partnership", "production workflow standardization"],
        ["Has both production and sales-network signals.", "Could buy equipment for production and influence labs through network."],
        ["partner/channel discussion around scanner-supported CAD/CAM workflow"],
        "Treat as high-priority European channel/production hybrid.",
    ),
    Prospect(
        "JDentalCare JD Milling Center",
        "Italy",
        "Europe",
        "Milling center / guided surgery support",
        "https://jdentalcare.com/en/jd-milling-center/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[1],
        "Search result said it supports dental clinics and laboratories with prosthetic restorations and complex guided surgery cases.",
        ["prosthetic restorations", "guided surgery", "clinics and laboratories"],
        ["implant case scanning", "surgical guide workflow", "lab scanner"],
        ["Guided surgery and restorations rely on precise digital data.", "Serving both clinics and labs expands use cases."],
        ["scanner demo for implant/restorative production"],
        "Identify if milling center is tied to implant ecosystem sales.",
    ),
    Prospect(
        "European Dental Lab",
        "Europe",
        "Europe",
        "Dental lab for clinics",
        "https://europeandentallab.com/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[1],
        "Search result said it delivers crowns, bridges, implants and veneers using CAD/CAM across Europe.",
        ["crowns", "bridges", "implants", "veneers", "CAD/CAM"],
        ["lab scanner", "cross-border digital workflow", "case intake"],
        ["CAD/CAM restorative lab is a standard DOF scanner target.", "Cross-Europe delivery implies standardized digital case handling."],
        ["scanner package for cross-border lab workflow"],
        "Verify scale and country base before outreach.",
    ),
    Prospect(
        "CLC Scientific",
        "Europe",
        "Europe",
        "CAD/CAM milling center",
        "https://clcscientific.com/en/cad-cam-milling-center/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[1],
        "Search result said the milling center uses latest technologies to support dental laboratories inside the digital workflow.",
        ["CAD/CAM milling", "dental laboratories", "digital workflow"],
        ["lab scanner", "digital workflow consulting", "milling-center intake"],
        ["Supporting dental labs in digital workflow creates scanner and consulting fit.", "B2B lab focus is a good sales signal."],
        ["scanner workflow bundle for labs supported by CLC"],
        "Check regional coverage and whether it distributes equipment.",
    ),
    Prospect(
        "Proxera",
        "Italy",
        "Europe",
        "Dental milling center",
        "https://www.proxera.it/en/manufacture/cad-cam-milling",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[1],
        "Search result said it processes cobalt chrome, titanium, zirconia, HIPC, PEEK and PMMA.",
        ["cobalt chrome", "titanium", "zirconia", "PEEK", "PMMA", "milling"],
        ["high-precision model scanning", "multi-material CAD/CAM workflow", "implant component workflow"],
        ["Multi-material production requires high-accuracy digital inputs.", "Titanium/implant work strengthens premium scanner fit."],
        ["scanner demo for multi-material and implant cases"],
        "High priority for European production-oriented pitch.",
    ),
    Prospect(
        "DentallGroup",
        "France",
        "Europe",
        "Dental prosthesis subcontracting / production center",
        "https://dentallgroup.com/en/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[1],
        "Search result said the production center works as a subcontractor for dental prosthesis laboratories.",
        ["CAD/CAM subcontracting", "dental prosthesis production", "lab partner"],
        ["lab scanner for incoming work", "outsourced production integration"],
        ["Subcontract production centers need accurate and repeatable case intake.", "Can become a channel to partner laboratories."],
        ["scanner + case intake proposal for subcontract center"],
        "Research French lab network links and current CAD/CAM equipment.",
    ),
    Prospect(
        "Zfx Dental",
        "Germany",
        "Europe",
        "Digital dental milling / outsourcing",
        "https://www.zfx-dental.com/en/milling",
        "B",
        "Direct buyer / benchmark",
        PLAYWRIGHT_SEARCH_QUERIES[9],
        "Search result said users can outsource the whole digital design and production process.",
        ["digital design", "production outsourcing", "milling"],
        ["scanner workflow compatibility", "production center integration"],
        ["Outsourcing model shows demand for digitized lab production.", "May be a partner or competitor depending on local channel."],
        ["ecosystem compatibility discussion"],
        "Qualify whether regional Zfx centers buy third-party scanners.",
    ),
    Prospect(
        "TTC Labs",
        "United Kingdom",
        "Europe",
        "Dental lab technology supplier",
        "https://www.ttclabs.co.uk/",
        "A",
        "Distributor / channel",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result said it supplies materials and machinery for dental laboratories and dental surgeons.",
        ["materials", "machinery", "dental laboratories", "dental surgeons"],
        ["distribution of DOF scanners", "lab equipment channel", "UK market access"],
        ["Supplier of lab machinery is a direct channel candidate.", "Can sell to both labs and surgeries."],
        ["UK distribution conversation for DOF scanner line"],
        "Prioritize as channel rather than end-user account.",
    ),
    Prospect(
        "TetraCam",
        "United Kingdom",
        "Europe",
        "Dental laboratory / lab-to-lab milling center",
        "https://www.tetracam.co.uk/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result said it is a dental laboratory and Lab2Lab milling centre, Trios ready and accepting intraoral scans.",
        ["Lab2Lab milling", "intraoral scans", "metal-free lab service"],
        ["scanner compatibility", "model scanning", "digital case intake"],
        ["Explicit intraoral scan acceptance means digital workflow maturity.", "Lab2Lab milling center is a high-fit DOF scanner buyer."],
        ["scanner pitch around accepting more scan/model sources"],
        "Contact lab owner/production team with UK lab-to-lab workflow angle.",
    ),
    Prospect(
        "ALS Densign Lab",
        "United Kingdom",
        "Europe",
        "Full-service dental lab / milling centre",
        "https://densignlab.co.uk/?service=the-milling-centre",
        "A",
        "Direct buyer / lab network",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result said it is a full-service dental laboratory serving dentists and dental laboratories across the UK.",
        ["full-service lab", "milling centre", "dentists and labs"],
        ["lab scanner", "multi-site lab workflow", "UK referral lab production"],
        ["Serving other labs raises throughput needs.", "ALS context suggests potential group-level procurement."],
        ["scanner evaluation for milling centre"],
        "Map ALS group ownership and central procurement.",
    ),
    Prospect(
        "Estetica Dental Lab",
        "United Kingdom",
        "Europe",
        "Dental milling center",
        "https://esteticadentallab.com/milling-center/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result said its milling center provides scanning and milling services, accepts STL files or models for scanning/design/milling.",
        ["scanning services", "milling services", "STL files", "models for scanning"],
        ["lab scanner", "model-to-STL conversion", "case intake workflow"],
        ["Explicit model scanning is a direct fit for DOF lab scanners.", "Milling workflow makes scanner value measurable."],
        ["scanner replacement/upgrade pitch for scanning service"],
        "Strong fit if current scanner is old or capacity-constrained.",
    ),
    Prospect(
        "HOIL Dental",
        "United Kingdom",
        "Europe",
        "Dental milling centre",
        "https://hoildental.com/",
        "A",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result described services from scanning, printing and designing to milling, coating and technical support.",
        ["scanning", "printing", "designing", "milling", "technical support"],
        ["lab scanner", "end-to-end digital workflow", "training/support partnership"],
        ["Scanning is explicitly part of their service mix.", "Technical support offering could turn them into a local advocate."],
        ["scanner demo plus technical support partnership"],
        "Pitch as both end-user and possible UK workflow reference site.",
    ),
    Prospect(
        "Rose Lane Dental Technology",
        "United Kingdom",
        "Europe",
        "Dental technology lab / milling centre",
        "https://roselanedentaltechnology.co.uk/service/milling-centre/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result said state-of-the-art CAD/CAM systems provide precise scans and custom designs for implant abutments, crowns and bridges.",
        ["CAD/CAM systems", "precise scans", "implant abutments", "crowns", "bridges"],
        ["lab scanner", "implant/restorative workflow", "CAD/CAM integration"],
        ["Precise scan language is a direct scanner buying signal.", "Implant abutment workflows need accuracy."],
        ["accuracy-led scanner demonstration"],
        "Check if site security blocks automated access; use search evidence for initial qualification.",
    ),
    Prospect(
        "Advanced Dental Laboratories",
        "United Kingdom",
        "Europe",
        "Dental laboratory / intraoral scan workflow",
        "https://www.advanceddentallaboratories.co.uk/product/intra-oral-scanning/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result said they are experienced with digital workflow and manufacture restorations within 3 working days.",
        ["intraoral scanning", "digital workflow", "restorations"],
        ["scanner compatibility", "fast-turnaround workflow", "digital case intake"],
        ["Fast turnaround depends on efficient scan handling.", "Intraoral scanning page suggests digital adoption."],
        ["scanner workflow benchmark for turnaround reduction"],
        "Qualify accepted scanner platforms and model-scanning needs.",
    ),
    Prospect(
        "MediMatch",
        "United Kingdom",
        "Europe",
        "Digital dental lab / scanner-aware lab",
        "https://medimatch.co.uk/",
        "B",
        "Direct buyer / channel",
        PLAYWRIGHT_SEARCH_QUERIES[2],
        "Search result mentioned Medit intraoral scanner and one-on-one online meetings.",
        ["digital dental lab", "Medit intraoral scanner discussion", "case support"],
        ["competitive scanner displacement", "lab scanner", "clinic scanner referrals"],
        ["Scanner-specific page indicates active scanner sales/support interest.", "Could be a channel if they advise clinics on scanners."],
        ["competitive positioning against Medit-focused workflows"],
        "Research whether MediMatch resells scanners or only accepts scanner files.",
    ),
    Prospect(
        "Corus Dental",
        "Europe",
        "Europe",
        "European dental laboratory group",
        "https://www.corusdental.com/en/",
        "A",
        "Enterprise direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[8],
        "Search result said Corus is an integrated network of reputed dental laboratories in Europe and accompanies dentists in digital transformation.",
        ["lab network", "digital transformation", "European laboratories"],
        ["enterprise scanner standardization", "multi-lab rollout", "digital workflow platform"],
        ["European lab group scale makes scanner standardization valuable.", "Digital transformation positioning suggests active equipment decisions."],
        ["enterprise scanner pilot with one Corus lab"],
        "Find group technology/procurement leader rather than individual lab contact.",
    ),
    Prospect(
        "Dental Technologies Group",
        "Europe",
        "Europe",
        "European dental laboratory group",
        "https://www.dentaltechnologies.com/",
        "A",
        "Enterprise direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[8],
        "Search result said it is European in scale, digital in mindset and built for the future.",
        ["lab group", "digital mindset", "European scale"],
        ["multi-site scanner standardization", "lab group workflow"],
        ["A growing European lab group is a strong strategic account.", "Digital positioning implies equipment modernization."],
        ["group-level scanner standardization pitch"],
        "Track acquisitions and identify CTO/operations lead.",
    ),
    Prospect(
        "Leixir Dental Laboratory Group",
        "Global / United States",
        "North America",
        "Dental laboratory group",
        "https://www.leixir.com/",
        "A",
        "Enterprise direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[8],
        "Search result said Leixir brings technology-based solutions to clients.",
        ["lab group", "technology-based solutions", "digital lab experience"],
        ["enterprise scanner deployment", "digital case workflow"],
        ["Lab group scale and technology positioning fit scanner sales.", "Potential multi-location account."],
        ["enterprise scanner pilot and support package"],
        "Map US and offshore production sites before outreach.",
    ),
    Prospect(
        "The Dental Laboratory Group",
        "United Kingdom",
        "Europe",
        "Dental laboratory group",
        "https://dentallaboratorygroup.com/digital-dentistry/",
        "A",
        "Direct buyer / enterprise buyer",
        PLAYWRIGHT_SEARCH_QUERIES[8],
        "Search result said its lab is equipped for digital dentistry and works with scans from any intraoral scanner.",
        ["digital dentistry", "intraoral scanner files", "lab support"],
        ["scanner compatibility", "lab scanner", "multi-scanner workflow"],
        ["Works with scanner data from many platforms, so compatibility matters.", "Digital dentistry page is a direct buying signal."],
        ["DOF scanner compatibility and open-workflow pitch"],
        "Approach around open ecosystem and support for mixed scanner inputs.",
    ),
    Prospect(
        "Permadental",
        "Germany / Netherlands",
        "Europe",
        "Dental laboratory",
        "https://permadental.de/",
        "B",
        "Direct buyer",
        "large European dental laboratory CAD CAM",
        "European dental laboratory brand included as scale target for digital production research.",
        ["dental restorations", "lab services", "digital production"],
        ["lab scanner", "central production workflow"],
        ["Large labs need repeatable scan-to-production workflows.", "Potential account if they operate centralized CAD/CAM production."],
        ["scanner modernization conversation"],
        "Verify digital equipment stack and procurement structure.",
    ),
    Prospect(
        "Flemming Dental",
        "Germany",
        "Europe",
        "Dental laboratory group",
        "https://www.flemming-dental.de/",
        "B",
        "Enterprise direct buyer",
        "German dental laboratory group digital dentistry",
        "German lab group included as scale target for centralized technology decisions.",
        ["dental lab services", "multi-location lab group", "digital workflows"],
        ["scanner standardization", "multi-site workflow"],
        ["Group scale can justify scanner fleet decisions.", "German production market is accuracy-oriented."],
        ["German-language scanner ROI package"],
        "Use local partner/distributor route if direct approach is slow.",
    ),
    Prospect(
        "Dentmill / Modern Dental Pacific",
        "Australia",
        "APAC",
        "Dental milling centre",
        "https://www.moderndentalpacific.com/brands/dentmill/",
        "A",
        "Direct buyer / enterprise group",
        PLAYWRIGHT_SEARCH_QUERIES[4],
        "Search result said Dentmill has a state-of-the-art milling centre with latest CAD/CAM technology and partners with labs and dentists across Australia.",
        ["CAD/CAM technology", "milling centre", "labs and dentists across Australia"],
        ["scanner workflow", "group account", "lab-to-dentist digital case flow"],
        ["Modern Dental Pacific/Dentmill combines scale and milling needs.", "Can be a gateway to broader Modern Dental group."],
        ["scanner pilot for Dentmill intake workflow"],
        "High-priority APAC target; map connection to Modern Dental Group.",
    ),
    Prospect(
        "XYZ Dental",
        "Australia",
        "APAC",
        "CAD/CAM distributor for labs and milling centres",
        "https://xyzdental.com.au/cad-cam-dentistry-solutions/laboratories/",
        "A",
        "Distributor / channel",
        PLAYWRIGHT_SEARCH_QUERIES[4],
        "Search result said Australian and New Zealand dental labs choose XYZ to support CAD-CAM dentistry.",
        ["CAD/CAM solutions", "laboratories", "Australia and New Zealand"],
        ["distribution of scanners", "ANZ channel", "lab equipment support"],
        ["CAD/CAM support provider is a natural channel for DOF equipment.", "Already speaks to labs and milling centers."],
        ["ANZ distribution conversation"],
        "Prioritize channel outreach with product margin/support story.",
    ),
    Prospect(
        "Swiss Dental Australia",
        "Australia",
        "APAC",
        "CAD/CAM dental laboratory",
        "https://www.swissdentalaustralia.com/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[4],
        "Search result said it is a pure CAD/CAM laboratory with internal milling and 3D-printing centre.",
        ["CAD/CAM laboratory", "internal milling", "3D printing", "implant reconstructions"],
        ["lab scanner", "implant model workflow", "3D printing/milling pipeline"],
        ["Internal milling and 3D printing are strong digital-production signals.", "Implant reconstructions need accurate model scans."],
        ["scanner demo for implant reconstruction workflow"],
        "Target technical director/lab owner.",
    ),
    Prospect(
        "CM Medical CAD/CAM Service",
        "Australia",
        "APAC",
        "CAD/CAM milling and printing service",
        "https://www.cm-medical.com.au/pages/cmservice",
        "B",
        "Direct buyer / channel",
        PLAYWRIGHT_SEARCH_QUERIES[4],
        "Search result said it supports Australian local dental labs.",
        ["CAD/CAM service", "milling", "printing", "local dental labs"],
        ["lab scanner", "service-center intake", "local lab channel"],
        ["Service providers supporting labs can become scanner users and referrers.", "Milling/printing signals digital production."],
        ["scanner workflow for Australian lab support"],
        "Check if CM Medical also sells equipment or only provides services.",
    ),
    Prospect(
        "K+C Dental & Precise Dental Milling",
        "Australia",
        "APAC",
        "Dental lab / milling and printing facility",
        "http://www.kcdental.com.au/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[4],
        "Search result said it offers latest CAD/CAM milling and printing machines for dental manufacture.",
        ["CAD/CAM milling", "printing", "dental manufacture"],
        ["lab scanner", "production workflow", "scanner-to-mill integration"],
        ["In-house milling/printing creates demand for scan/design data.", "Direct local production account."],
        ["scanner demo focused on production integration"],
        "Verify active site/contact and current equipment age.",
    ),
    Prospect(
        "Australia Dental Milling Centre (ADMC)",
        "Australia",
        "APAC",
        "Dental milling centre",
        "https://www.dentalmillingcentre.com.au/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[4],
        "Search result identified a dedicated dental milling centre in NSW.",
        ["dental milling centre", "Australian lab service"],
        ["lab scanner", "case intake", "production QC"],
        ["Dedicated milling centers are natural scanner buyers.", "Local service center may value fast support and reliability."],
        ["scanner workflow for milling center"],
        "Qualify actual production scale and target labs.",
    ),
    Prospect(
        "Apex Dental Laboratory",
        "Australia",
        "APAC",
        "Dental lab with CAD/CAM service",
        "https://apexdental.com.au/lab-services/cad-cam/",
        "B",
        "Direct buyer",
        PLAYWRIGHT_SEARCH_QUERIES[4],
        "Search result said Apex receives 3Shape Communicate or STL files and manufactures appliances through milling or printing.",
        ["3Shape Communicate", "STL files", "milling", "printing"],
        ["open workflow scanner", "STL case intake", "lab scanner"],
        ["Explicit STL/3Shape intake shows digital workflow maturity.", "Milling/printing makes scanner adoption relevant."],
        ["open STL workflow pitch"],
        "Approach with compatibility and turnaround story.",
    ),
    Prospect(
        "Dental Axess",
        "Australia / Global",
        "APAC",
        "Digital dentistry distributor",
        "https://www.dentalaxess.com/",
        "A",
        "Distributor / channel",
        "digital dentistry distributor Australia CAD CAM scanner",
        "Digital dentistry distributor included as channel target for scanner sales.",
        ["digital dentistry equipment", "CAD/CAM", "scanner-related solutions"],
        ["DOF scanner distribution", "regional support/channel coverage"],
        ["Digital dentistry distributors can open many clinic/lab doors.", "Australia/NZ support gap may be addressed through local channel."],
        ["channel partnership discussion"],
        "Evaluate brand conflicts and regional exclusivity.",
    ),
    Prospect(
        "CAD-Ray",
        "United States",
        "North America",
        "Digital dentistry distributor / education company",
        "https://www.cad-ray.com/",
        "A",
        "Distributor / channel",
        PLAYWRIGHT_SEARCH_QUERIES[6],
        "Search result said CAD-Ray specializes in digital imaging, CAD/CAM, guided implantology and CT technologies.",
        ["digital imaging", "CAD/CAM", "guided implantology", "education", "distribution"],
        ["scanner distribution", "education-led sales", "US channel"],
        ["Education-led distributor can accelerate adoption.", "Their audience overlaps DOF scanner buyers."],
        ["US reseller/education partner pitch"],
        "Check current scanner brands and channel conflict.",
    ),
    Prospect(
        "Dental Benmayor",
        "Spain",
        "Europe",
        "Dental equipment distributor",
        "https://dental.benmayor.com/en/4078-digital-imaging-and-cad-cam",
        "B",
        "Distributor / channel",
        PLAYWRIGHT_SEARCH_QUERIES[6],
        "Search result said it offers digital imaging and CAD/CAM products, including high precision intraoral scanners such as Medit.",
        ["digital imaging", "CAD/CAM", "intraoral scanners", "equipment sales"],
        ["scanner channel", "Medit displacement/portfolio expansion", "Spanish market access"],
        ["Already selling scanners means buyer audience exists.", "Could add DOF lab scanner if portfolio lacks equivalent strength."],
        ["portfolio expansion pitch for lab scanners"],
        "Position around lab scanner differentiation, not commodity intraoral scanner.",
    ),
    Prospect(
        "Henry Schein Dental",
        "United States / Global",
        "Global",
        "Dental distributor",
        "https://www.henryschein.com/us-en/dental/c/digital-technology",
        "A",
        "Strategic distributor",
        "global dental distributor digital dentistry equipment",
        "Global dental distributor with digital technology category.",
        ["digital technology", "dental equipment", "global distribution"],
        ["major distributor channel", "enterprise reseller", "after-sales network"],
        ["Global scale could unlock multiple regions but requires channel readiness.", "DOF needs strong support, margin and differentiation story."],
        ["strategic distribution briefing"],
        "Long-cycle target; pursue after regional proof points.",
    ),
    Prospect(
        "Patterson Dental",
        "United States",
        "North America",
        "Dental distributor",
        "https://www.pattersondental.com/Supplies/Equipment-Digital-Dentistry",
        "B",
        "Distributor / channel",
        "US dental distributor digital dentistry equipment",
        "US dental distributor with equipment and digital dentistry portfolio.",
        ["digital dentistry equipment", "dental supplies", "technology sales"],
        ["US reseller channel", "scanner equipment sales"],
        ["Distributor audience overlaps dental labs and clinics.", "Could become channel if DOF has US compliance/support readiness."],
        ["regional reseller pitch"],
        "Check current scanner/milling partnerships and exclusivity.",
    ),
    Prospect(
        "Benco Dental",
        "United States",
        "North America",
        "Dental distributor",
        "https://www.benco.com/dental-equipment/digital-dentistry/",
        "B",
        "Distributor / channel",
        "US dental distributor digital dentistry CAD CAM scanner",
        "US distributor with digital dentistry/equipment category.",
        ["digital dentistry", "dental equipment", "practice technology"],
        ["scanner distribution", "regional reseller relationship"],
        ["Equipment distributor can sell scanner hardware and support adoption.", "Potential fit if DOF needs US regional channel."],
        ["scanner channel qualification call"],
        "Qualify product portfolio gaps and lab-focused sales coverage.",
    ),
    Prospect(
        "Unident",
        "Nordics",
        "Europe",
        "Dental distributor",
        "https://www.unident.se/",
        "B",
        "Distributor / channel",
        "Nordic dental distributor digital dentistry scanner",
        "Nordic dental distributor included as regional channel candidate.",
        ["dental equipment", "digital dentistry", "Nordic market"],
        ["Nordic scanner channel", "regional service/support"],
        ["Regional distributors can solve local service and language barriers.", "Nordics have high digital adoption."],
        ["Nordic distribution screening"],
        "Verify current scanner portfolio and lab customer base.",
    ),
]


def slugify(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[^a-z0-9가-힣]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")[:90]


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def wrap_md(value: str) -> str:
    return "\n".join(textwrap.wrap(value, width=110, replace_whitespace=False)) if value else ""


def fetch_page(url: str) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "url": url, "final_url": url, "title": "", "snippets": [], "error": ""}
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=14, allow_redirects=True)
        result["status_code"] = response.status_code
        result["final_url"] = response.url
        if response.status_code >= 400:
            result["error"] = f"HTTP {response.status_code}"
            return result
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        result["title"] = compact(title)
        lines = [compact(line) for line in soup.get_text("\n").splitlines()]
        seen: set[str] = set()
        snippets: list[str] = []
        for line in lines:
            if len(line) < 28 or len(line) > 240:
                continue
            if not KEYWORDS.search(line):
                continue
            lower = line.lower()
            if lower in seen:
                continue
            seen.add(lower)
            snippets.append(line)
            if len(snippets) >= 5:
                break
        result["snippets"] = snippets
        result["ok"] = True
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def enrich_prospects() -> list[Prospect]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_page, prospect.url): prospect for prospect in PROSPECTS}
        for future in as_completed(futures):
            prospect = futures[future]
            prospect.fetched = future.result()
    return PROSPECTS


def evidence_lines(prospect: Prospect) -> list[str]:
    lines: list[str] = []
    for snippet in prospect.fetched.get("snippets") or []:
        lines.append(snippet)
    if prospect.search_evidence:
        lines.append(prospect.search_evidence)
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        value = compact(line)
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        out.append(value)
        if len(out) >= 6:
            break
    return out


def score(prospect: Prospect) -> int:
    value = {"A": 85, "B": 70, "C": 55}.get(prospect.priority, 60)
    if "Distributor" in prospect.customer_type or "channel" in prospect.customer_type.lower():
        value += 4
    if "Enterprise" in prospect.customer_type:
        value += 6
    if prospect.fetched.get("ok"):
        value += 3
    if any("scanner" in s.lower() or "scan" in s.lower() for s in evidence_lines(prospect)):
        value += 4
    return min(value, 98)


def card_markdown(index: int, prospect: Prospect) -> str:
    evidences = evidence_lines(prospect)
    fetched = prospect.fetched or {}
    source_title = fetched.get("title") or urlparse(prospect.url).netloc
    return f"""# {prospect.name}

## 고객카드
- 우선순위: {prospect.priority} ({score(prospect)}/100)
- 지역/국가: {prospect.region} / {prospect.country}
- 세그먼트: {prospect.segment}
- 고객 유형: {prospect.customer_type}
- 공식/확인 URL: [{source_title}]({prospect.url})
- 발견 검색어: `{prospect.discovery_query}`

## 무엇을 사고 파는 회사인가
{chr(10).join(f"- {item}" for item in prospect.buys_sells)}

## DOF 관점의 구매 가능성
{chr(10).join(f"- {item}" for item in prospect.why_customer)}

## DOF가 제안할 수 있는 것
{chr(10).join(f"- {item}" for item in prospect.dof_fit)}

## 1차 제안 패키지
{chr(10).join(f"- {item}" for item in prospect.suggested_offer)}

## 공개 근거
{chr(10).join(f"- {line}" for line in evidences)}

## 다음 액션
- {prospect.next_action}

## 리서치 상태
- 공식 페이지 접근: {"성공" if fetched.get("ok") else "실패/제한"}
- 최종 URL: {fetched.get("final_url") or prospect.url}
- 비고: {prospect.notes or "-"}
"""


def build_search_log() -> str:
    lines = [
        "# Playwright MCP 검색 로그",
        "",
        "이 리서치는 Playwright MCP 브라우저 세션으로 Bing 검색 결과를 직접 열어 후보군을 만든 뒤, 공식 사이트 공개 문구를 보조 확인했다.",
        "",
        "## 사용 검색어",
    ]
    for query in PLAYWRIGHT_SEARCH_QUERIES:
        lines.append(f"- `{query}`")
    lines += [
        "",
        "## 고객 판단 기준",
        "- 직접 구매 후보: 자체 CAD/CAM, 밀링, 스캔, 3D 프린팅, 보철 제작 또는 lab-to-lab 서비스를 운영하는 회사.",
        "- 채널 후보: CAD/CAM 장비, 디지털 덴티스트리, 스캐너, 밀링기 또는 랩 장비를 유통/교육/지원하는 회사.",
        "- 엔터프라이즈 후보: 여러 랩을 묶은 그룹으로 장비 표준화, 다점포 지원, 대량 생산 워크플로우 가능성이 있는 회사.",
    ]
    return "\n".join(lines) + "\n"


def index_markdown(prospects: list[Prospect]) -> str:
    by_segment = Counter(p.segment for p in prospects)
    by_region = Counter(p.region for p in prospects)
    by_type = Counter(p.customer_type for p in prospects)
    high = [p for p in prospects if p.priority == "A"]
    lines = [
        "# DOF 해외 잠재 고객사 발굴",
        "",
        f"- 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}",
        f"- 총 후보: {len(prospects)}개",
        f"- A 우선순위: {len(high)}개",
        "- 기준 회사: DOF",
        "",
        "## 요약 판단",
        "- 1순위는 자체 밀링센터/디지털 생산센터를 운영하거나 lab-to-lab 생산을 하는 해외 치과기공소다.",
        "- 2순위는 여러 랩을 가진 그룹형 고객이다. 장비 표준화와 다점포 지원을 묶어 접근해야 한다.",
        "- 3순위는 CAD/CAM/스캐너 장비 유통사다. 직접 구매보다 현지 채널 확보 가치가 크다.",
        "",
        "## 지역별 분포",
    ]
    for region, count in by_region.most_common():
        lines.append(f"- {region}: {count}개")
    lines += ["", "## 고객 유형별 분포"]
    for customer_type, count in by_type.most_common():
        lines.append(f"- {customer_type}: {count}개")
    lines += ["", "## 세그먼트별 분포"]
    for segment, count in by_segment.most_common():
        lines.append(f"- {segment}: {count}개")
    lines += [
        "",
        "## 우선 공략 리스트",
        "",
        "| 우선 | 점수 | 회사 | 국가 | 유형 | 카드 |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for idx, prospect in enumerate(sorted(prospects, key=lambda p: (-score(p), p.name)), start=1):
        slug = f"{idx:02d}-{slugify(prospect.name)}.md"
        lines.append(
            f"| {prospect.priority} | {score(prospect)} | {prospect.name} | {prospect.country} | "
            f"{prospect.customer_type} | [card](cards/{slug}) |"
        )
    lines += [
        "",
        "## 바로 실행할 영업 가설",
        "- 북미/영국/호주 밀링센터에는 `모델 스캔 + STL 수신 + 밀링 전 QC` 흐름을 묶어 장비 ROI를 설명한다.",
        "- 유럽 랩 그룹에는 단일 장비 판매보다 `표준화된 스캐너 세트 + 다점포 교육/지원`으로 접근한다.",
        "- CAD/CAM 유통사에는 DOF가 제공할 수 있는 마진, 데모 장비, 교육 콘텐츠, A/S 체계를 먼저 제시한다.",
        "- 경쟁 스캐너를 이미 다루는 회사에는 교체보다 `랩 스캐너 보강`, `특정 indication`, `오픈 STL 호환성`을 앞세운다.",
        "",
        "## 파일 구조",
        "- `cards/`: 업체별 고객카드",
        "- `data/prospects.json`: 카드 생성용 정형 데이터와 수집 상태",
        "- `playwright_search_log.md`: Playwright MCP 검색어와 판단 기준",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(prospects: list[Prospect]) -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ordered = sorted(prospects, key=lambda p: (-score(p), p.name))
    records: list[dict[str, Any]] = []
    for index, prospect in enumerate(ordered, start=1):
        card_name = f"{index:02d}-{slugify(prospect.name)}.md"
        card_path = CARDS_DIR / card_name
        card_path.write_text(card_markdown(index, prospect), encoding="utf-8")
        records.append(
            {
                **{k: v for k, v in prospect.__dict__.items() if k != "fetched"},
                "score": score(prospect),
                "card": str(card_path),
                "fetched": prospect.fetched,
                "evidence": evidence_lines(prospect),
            }
        )
    DATA_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    SEARCH_LOG_PATH.write_text(build_search_log(), encoding="utf-8")
    INDEX_PATH.write_text(index_markdown(ordered), encoding="utf-8")


def main() -> None:
    prospects = enrich_prospects()
    write_outputs(prospects)
    ok = sum(1 for p in prospects if p.fetched.get("ok"))
    print(json.dumps({"prospects": len(prospects), "official_pages_ok": ok, "out": str(OUT_ROOT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
