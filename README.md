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

1. **Cryptographic Auditability & Snapshot Integrity (IOSCO Principle 15)**:
   - Every point-in-time snapshot stores its **complete raw constituent observations array**.
   - Checksums are computed deterministically as the **SHA-256 hash** of the canonical observation JSON payload.
   - Built-in verification endpoint (`GET /api/snapshots/{id}/verify`) allows any user or risk committee to audit and re-derive published settlement values directly from raw constituents.

2. **Physical Deliverable Contract Unit Resolution**:
   - Differentiates clustered **HGX 8x nodes** (900 GB/s NVLink 4, 3.2 Tbps InfiniBand/EFA) from **1x Standalone Pods**, **PCIe Gen5**, and **NVL** modules.
   - Eliminates pooling bias between high-end distributed training clusters and single inference cards.

3. **Quantitative Pricing & Term Structure Volatility Diffusion**:
   - **Normalized Settlement Rate**: $$\text{Normalized Rate} = \frac{\text{Server Hourly Rate}}{\text{Published GPU Count}}$$
   - **Matched-Provider Technological Deflation ($d$)**: Computes rental-price compression across generational pairs ($A100 \rightarrow H100 \rightarrow H200 \rightarrow B200 \rightarrow B300$) strictly within matched providers to prevent provider mix distortion.
   - **Model-Implied Forward Curve with $\sigma \sqrt{T}$ Volatility Diffusion**:
     $$F(T) = S_0 \times [(1 + c) \times (1 - d)]^T$$
     $$\text{Upper Band}(T) = F(T) \times \exp\left(+ \sigma \sqrt{T}\right), \quad \text{Lower Band}(T) = F(T) \times \exp\left(- \sigma \sqrt{T}\right)$$
     where $S_0$ is the cash anchor median for the specific deliverable SKU, $c$ is the annual carry & scarcity rate, $d$ is data-derived technological decay, and $\sigma$ is spot price dispersion volatility expanding over longer tenors.

4. **Institutional Stress Testing & Diagnostic Instruments**:
   - **Source Ablation Engine**: Assesses the price impact ($\Delta\%$) when individual providers are excluded from the index.
   - **Methodology Sensitivity Matrix**: Compares 6 aggregation methodologies (Robust Median, 10% Trimmed Mean, 20% Trimmed Mean, Provider-Balanced, GPU-Weighted, Simple Mean) in real time.
   - **Provenance Ledger**: Transparent unadjusted unit math and direct provider source URLs.

5. **Continuous Multi-Provider Resync Engine**:
   - Live adapters for Azure Retail Prices REST API, RunPod catalog, CoreWeave node rates, AWS Capacity Blocks, GCP Accelerator VMs, and Lambda Labs.
   - Intelligent diff engine: detects added, updated, unchanged, and deprecated rates with full audit logs.

6. **Modern Web Terminal Dashboard**:
   - Dark-mode financial terminal UI with one-click snapshot verification and constituent audit inspection.
   - Interactive Forward Curve explorer with configurable horizon, cadence, carry, and cash anchor.
   - Multi-column sortable and searchable market tape with CSV and JSON exports.

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

## Benchmark Integrity & Audit Reproducibility

Financial compute benchmarks must satisfy the same auditability standards as established physical commodity indexes (such as **IOSCO Principle 15** and the **EU/UK Benchmarks Regulation**). FSKU is engineered around five fundamental reproducibility principles:

1. **Constituent Audit Trail & Immutability**:
   - Every point-in-time snapshot contains the complete raw observation array (`observations: [...]`).
   - Checksums are computed as the SHA-256 hash of the canonical JSON representation of those raw constituents.
   - Any market participant can verify any historical snapshot via `GET /api/snapshots/{id}/verify` or the Web UI, confirming that published settlement values reconcile to the cent from their constituent inputs.

2. **Physical Deliverable Contract Unit Resolution**:
   - Pooling heterogeneous hardware into generic buckets introduces fatal basis risk.
   - FSKU strictly differentiates **Form Factor** (SXM5, SXM6, PCIe Gen5, NVL, OAM), **Interconnect** (900 GB/s NVLink 4, 1.8 TB/s NVLink 5, PCIe Bus, Infinity Fabric), and **Node Topology** (HGX 8x Clustered with 3.2 Tbps InfiniBand/RoCE vs 1x Standalone Virtualized Pods).

3. **Lognormal Volatility Diffusion Fan Chart ($\sigma \sqrt{T}$)**:
   - In forward term structure modeling, uncertainty expands over longer delivery horizons.
   - FSKU models forward uncertainty using a lognormal diffusion structure:
     $$\text{Upper Band}(T) = F(T) \cdot \exp\left(+ \sigma \sqrt{T}\right), \quad \text{Lower Band}(T) = F(T) \cdot \exp\left(- \sigma \sqrt{T}\right)$$
     where $\sigma = \frac{\ln(Q_{75}/Q_{25})}{1.349}$ is derived from observed cross-provider spot price dispersion.

4. **Matched-Provider Technological Deflation ($d$)**:
   - Technological price deflation ($A100 \rightarrow H100 \rightarrow H200 \rightarrow B200 \rightarrow B300$) is computed strictly across paired observations *within the same provider* to prevent provider mix shifts from distorting generational price compression ratios.

5. **Source Ablation Stress Testing & Methodology Sensitivity**:
   - FSKU provides real-time ablation diagnostic engines that systematically remove each provider from the dataset, measuring the resulting price delta ($\Delta\%$) to ensure no single data contributor can manipulate or disproportionately bias the benchmark.

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
