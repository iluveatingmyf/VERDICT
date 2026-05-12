# Dataset Setup

## Rule corpora (logic) — clone once, already gitignored

```bash
mkdir -p datasets && cd datasets
git clone --depth 1 https://github.com/IoTBench/IoTBench-test-suite
git clone --depth 1 https://github.com/SmartAppZoo/SmartAppZoo
git clone --depth 1 https://github.com/EPMatt/awesome-ha-blueprints
```

Expected layout after cloning:

```
datasets/
├── IoTBench-test-suite/
├── SmartAppZoo/
└── awesome-ha-blueprints/
```

IFTTT is **not used** in the starter corpus (§9.1 — expressive power too weak for interaction
prototyping). May be added later for popularity statistics in the paper.

---

## Activity corpora (situation timelines) — manual acquisition required

These require registration or direct download. **Never commit dataset files** — `datasets/` is
in `.gitignore`. The research lead performs the acquisition; document the download date and
version in a local `datasets/README_local.txt` (also gitignored).

### CASAS Twor (`datasets/casas_twor/`)

**What it is**: 2-resident smart home dataset with per-resident activity ground-truth labels.
Primary source for C1 (elderly + caregiver) and C2 (couple) situation templates.

**Acquisition**:
1. Visit <https://casas.wsu.edu/datasets/>
2. Create a free account (name + institution required).
3. Request access to **CASAS TWOR 2009** (or the most recent Twor multi-resident release).
4. Download and extract to `datasets/casas_twor/`.

**Expected files**: `*.csv` sensor log + `*.txt` activity annotation per resident.

---

### CASAS Multi-resident ADL (`datasets/casas_multi_adl/`)

**What it is**: Smaller multi-resident ADL dataset; designed specifically for multi-occupant
activity recognition. Use as a secondary source to avoid single-dataset bias (§10.2).

**Acquisition**:
1. Same CASAS account as above.
2. Request access to **Multi-Resident** dataset under the CASAS portal.
3. Extract to `datasets/casas_multi_adl/`.

---

### ARAS House A (`datasets/aras_house_a/`) and House B (`datasets/aras_house_b/`)

**What it is**: Two 2-resident homes, minute-level binary sensor readings + dual activity labels
(one label per resident per minute). Good for C2 (cohabitants) and C3 (parent + child) templates.

**Acquisition** (no registration required as of last check):
1. Visit <https://www.cmpe.boun.edu.tr/aras/>
2. Download **House A** and **House B** archives directly.
3. Extract to `datasets/aras_house_a/` and `datasets/aras_house_b/` respectively.

**Expected files**: `DAY_*.txt` (sensor + activity columns), `README` with sensor layout.

---

## Sensor → capability mapping

After datasets are present, review and extend `verdict/data/sensor_capability_map.yaml` to
cover the specific sensor IDs in each dataset. The CASAS sensor naming convention
(`M001`, `D001`, etc.) is pre-populated; ARAS integer IDs require manual mapping based on
the house layout files.

---

## Verification checklist

Run after acquisition to confirm layout is correct:

```bash
ls datasets/IoTBench-test-suite/   # should contain SmartApp subdirs
ls datasets/SmartAppZoo/           # should contain *.groovy files
ls datasets/awesome-ha-blueprints/ # should contain blueprints/ subdir
ls datasets/casas_twor/            # should contain sensor log + annotation files
ls datasets/casas_multi_adl/       # should contain activity data files
ls datasets/aras_house_a/          # should contain DAY_*.txt files
ls datasets/aras_house_b/          # should contain DAY_*.txt files
```
