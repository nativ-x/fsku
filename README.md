# FSKU (Futures SKU & Compute Benchmark Platform)

[![Release](https://img.shields.io/badge/Release-v0.9.0-38ef7d.svg)](https://github.com/nativ-x/fsku/releases)
[![Built by NATIVX](https://img.shields.io/badge/Built%20by-NATIVX-white.svg)](https://nativx.net)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com)
[![NoSQL Document Store](https://img.shields.io/badge/Database-Embedded%20NoSQL-orange.svg)]()
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**FSKU** is an open-source compute SKU normalization, market settlement intelligence, and implied forward curve platform **built by [NATIVX](https://nativx.net)**. It ingests public rates across cloud providers (RunPod, CoreWeave, AWS, Google Cloud, Azure, Lambda Labs), normalizes them into standardized `$/GPU-hour` settlement units, stores time-series data in an embedded lightweight NoSQL database, and models implied cross-generation forward term structures.

---

## Key Capabilities

1. **Lightweight Embedded NoSQL Database (`FSKUDb`)**:
   - Zero-dependency document store storing `observations`, `snapshots`, `specs`, `sources`, and `sync_logs`.
   - Thread-safe, atomic transactional file writes (`.tmp` + atomic rename/fsync).
   - Rich query filters (`$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$contains`, `$regex`), sorting, and pagination.
   - Point-in-time immutable snapshot engine with SHA-256 integrity checksums.

2. **Continuous Multi-Provider Resync Engine**:
   - Live adapters for Azure Retail Prices REST API, RunPod catalog, CoreWeave node rates, AWS Capacity Blocks, GCP Accelerator VMs, and Lambda Labs.
   - Intelligent diff engine: detects added, updated, unchanged, and deprecated rates.
   - Audit logging with execution duration, errors, and diff statistics.
   - Resync via CLI (`fsku sync`), REST API (`POST /api/sync`), or the web dashboard.

3. **Quantitative Pricing & Forward Curve Term Structure**:
   - **Normalized Settlement Rate**: $$\text{Normalized Rate} = \frac{\text{Server Hourly Rate}}{\text{Published GPU Count}}$$
   - **Matched-Provider Technological Deflation ($d$)**: Computes rental-price compression across generational pairs ($A100 \rightarrow H100 \rightarrow H200 \rightarrow B200 \rightarrow B300$) solely within matched providers to avoid provider bias.
   - **Model-Implied Forward Curve**:
     $$F(T) = S_0 \times [(1 + c) \times (1 - d)]^T$$
     where $S_0$ is the cash anchor median, $c$ is the annual carry & scarcity rate, $d$ is data-derived technological decay, and $T$ is the tenor horizon in years.

4. **Modern Web Terminal Dashboard**:
   - Dark-mode financial terminal UI.
   - Live on-demand Resync button with instant feedback toast notifications.
   - Interactive Forward Curve explorer with configurable horizon, cadence, carry, and cash anchor.
   - Multi-column sortable and searchable market tape.
   - One-click CSV and JSON exports for observations and forward curves.

---

## Quickstart

### 1. Installation

Clone or open the repository:

```bash
git clone https://github.com/nativ-x/fsku.git
cd sku_futures
```

Install requirements in your virtual environment:

```bash
pip install -r requirements.txt
```

### 2. Launch the Web Platform

Start the server and web dashboard:

```bash
# Using Python CLI
python fsku_cli.py serve --port 8000

# Or using runner scripts:
./run.sh         # Linux / macOS / WSL
run.bat          # Windows CMD
.\run.ps1        # Windows PowerShell
```

Visit **http://localhost:8000** in your browser. Interactive API documentation is available at **http://localhost:8000/api/docs**.

---

## Product Views & Architecture

The platform provides a cohesive financial terminal workflow structured around the benchmark pipeline:

**Public Data In → Normalized GPU Pricing → SKU Index → Historical Benchmark → Forward Curve**

| View | Purpose & Functionality |
| :--- | :--- |
| **1. Market Overview** | Master market dashboard showing all tracked GPU SKUs, current index prices, 24h changes, price dispersion, observation counts, statistical confidence ratings (`HIGH`, `MODERATE`, `LOW (SPARSE)`), and market status (`ACTIVE`, `INDICATIVE`, `EMERGING`). |
| **2. SKU Detail View** | Deep dive for any selected GPU (H100 SXM, H100 PCIe, H200, B200, B300, A100, MI300X) pairing official hardware engineering specs (VRAM, memory bandwidth, TDP, peak compute) with price dispersion metrics, memory economics ($/GB, GB/$), and contributing quotes. |
| **3. Spot Index View** | Granular breakdown of reference prices in $/GPU-hour across 6 configurable methodologies (Robust Median, 10% Trimmed Mean, 20% Trimmed Mean, Provider-Balanced, GPU-Count Weighted, Simple Mean) with full mathematical formulation. |
| **4. Historical Index View** | Time-series benchmark trajectories across quarterly snapshots with point-in-time index replay, rate deflation metrics, and SHA-256 snapshot audit checksums. |
| **5. Forward Curve View** | Model-implied term structure calculator across future delivery horizons (Cash, 1M, 3M, 6M, 12M, 18M, 24M, 36M, 48M, 60M) with IQR confidence bands, matched-provider tech deflation ($d$), and configurable annual carry/scarcity ($c$). |
| **6. Curve Comparison View** | Simultaneous multi-curve charting comparing H100, H200, B200, B300, and A100 forward curves side-by-side with cross-SKU tenor alignment matrix and relative value ratios (e.g. B200/H100 premium over time). |
| **7. Provider Comparison View** | Cross-provider pricing matrix across hyperscalers (AWS, GCP, Azure), specialized clouds (CoreWeave, RunPod, Lambda Labs), and secondary marketplaces with delta vs benchmark index ($\Delta\%$). |
| **8. Methodology Sensitivity View** | Quantitative sensitivity matrix demonstrating how 6 different aggregation formulas affect the spot index for every SKU with maximum divergence percentages. |
| **9. Source Ablation View** | Benchmark resilience stress testing showing the exact price impact ($\Delta\$$, $\Delta\%$) when individual providers or feeds are excluded from the index calculation. |
| **10. Market Tape View** | Full transparent access to all normalized underlying observations with instant multi-column sorting, live search, and filters by SKU, provider, and contract basis. |
| **11. Data Provenance View** | Traceability ledger showing direct provider URLs, observation timestamps, contract bases, geographical regions, gross instance prices, and normalization formulas applied. |
| **12. Methodology Documentation** | Plain-English institutional specification explaining unit normalization, outlier filtering, equal vs volume weighting, technological deflation inference, and forward curve formulations. |

---

## CLI Reference

The `fsku` CLI offers complete programmatic command capabilities:

| Command | Description | Example |
| :--- | :--- | :--- |
| `fsku stats` | Macro tape summary, dispersion ratio, and database stats | `python fsku_cli.py stats` |
| `fsku index` | Compute spot index summaries across all GPU SKUs | `python fsku_cli.py index --method provider_balanced` |
| `fsku sensitivity`| Show index price sensitivity matrix across 6 methodologies | `python fsku_cli.py sensitivity` |
| `fsku ablation` | Stress-test index stability by simulating provider exclusions | `python fsku_cli.py ablation --sku "H100 SXM"` |
| `fsku forward` | Derive and render implied forward term structure table | `python fsku_cli.py forward --gpu H100 --horizon 36` |
| `fsku compare` | Align and compare multiple GPU forward curves simultaneously | `python fsku_cli.py compare --families H100,H200,B200` |
| `fsku list` | Render sortable price observations table in terminal | `python fsku_cli.py list --gpu H100 --basis On-demand` |
| `fsku sync` | Trigger live multi-provider feed resynchronization | `python fsku_cli.py sync --label "Weekly sync"` |
| `fsku snapshot list`| List historical point-in-time market snapshots | `python fsku_cli.py snapshot list` |
| `fsku serve` | Start FastAPI REST server and interactive web dashboard | `python fsku_cli.py serve --port 8000` |

---

## REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status and database statistics |
| `GET` | `/api/kpis` | Executive metrics, dispersion ratio, memory economics |
| `GET` | `/api/index/summary` | Spot index summaries across all tracked SKUs (supports `method=`) |
| `GET` | `/api/index/sensitivity` | Index price sensitivity across 6 calculation methodologies |
| `GET` | `/api/index/ablation` | Source ablation impact matrix (supports `sku=`) |
| `GET` | `/api/providers/matrix` | Cross-provider pricing matrix with index deltas |
| `GET` | `/api/history` | Historical index benchmark time-series across snapshots |
| `GET` | `/api/observations` | Query price observations (filter by gpu, provider, basis, region, search) |
| `POST` | `/api/observations` | Insert custom or negotiated observation |
| `GET` | `/api/forward-curve` | Calculate implied forward curve for specified GPU family |
| `GET` | `/api/forward-curves/compare`| Simultaneously calculate and align multi-GPU forward curves |
| `POST` | `/api/sync` | Trigger an on-demand multi-provider market feed resync |
| `GET` | `/api/sync/history` | Audit log of previous resync operations |
| `GET` | `/api/snapshots` | List point-in-time immutable market snapshots |
| `GET` | `/api/specs` | Hardware engineering specs (H100, H200, B200, B300, MI300X) |
| `GET` | `/api/sources` | Provenance ledger and primary source links |
| `GET` | `/api/export/csv` | Download active tape observations as CSV |
| `GET` | `/api/export/forward-csv`| Download forward curve term structure as CSV |
| `GET` | `/api/export/history-csv`| Download historical index benchmark series as CSV |

---

## Codebase Architecture

```
sku_futures/
├── fsku/
│   ├── __init__.py
│   ├── api/                      # FastAPI REST application
│   │   ├── app.py                # Server setup, static mounting, CORS
│   │   └── routes.py             # All API endpoints
│   ├── cli/                      # Typer & Rich CLI
│   │   └── main.py               # CLI commands & formatting
│   ├── core/                     # Core domain & calculation engines
│   │   ├── database.py           # FSKUDb lightweight NoSQL document store
│   │   ├── forward_curve.py      # Implied forward term structure engine
│   │   ├── models.py             # Pydantic domain models & schemas
│   │   └── pricing.py            # Normalization, quantiles, and dispersion
│   ├── data/
│   │   └── seeds/                # Out-of-the-box verified seed checkpoints
│   │       ├── observations.json
│   │       ├── sources.json
│   │       └── specs.json
│   ├── sync/                     # Multi-provider resynchronization
│   │   ├── base.py               # Base adapter class
│   │   ├── engine.py             # Orchestrator & diff processor
│   │   ├── specs_catalog.py      # Hardware catalog sync
│   │   └── providers/            # Provider adapters
│   │       ├── azure.py          # Azure Retail Prices REST API
│   │       ├── aws.py            # AWS EC2 & Capacity Blocks
│   │       ├── coreweave.py      # CoreWeave HGX server rates
│   │       ├── gcp.py            # Google Cloud Accelerator VMs
│   │       ├── lambda_cloud.py   # Lambda Labs Cloud
│   │       └── runpod.py         # RunPod GPU catalog
│   └── web/                      # Interactive Financial Terminal Dashboard
│       └── index.html
├── data/                         # Local NoSQL document database store
├── tests/                        # Comprehensive test suite
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_forward_curve.py
│   └── test_sync.py
├── fsku_cli.py                   # Root CLI executable runner
├── pyproject.toml                # Package configuration
├── requirements.txt              # Pinned dependencies
├── Dockerfile                    # Containerization
├── docker-compose.yml
├── run.bat                       # Windows launcher
├── run.ps1                       # PowerShell launcher
└── run.sh                        # Linux / macOS / WSL launcher
```

---

## Testing

Run the test suite:

```bash
pytest tests/
```

Or via WSL:

```bash
wsl bash -c "cd /mnt/d/apps/sku_futures && pytest tests/"
```

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
