# Dataset Setup

## Rule corpora

```bash
mkdir -p datasets && cd datasets
git clone --depth 1 https://github.com/IoTBench/IoTBench-test-suite
git clone --depth 1 https://github.com/SmartAppZoo/SmartAppZoo
git clone --depth 1 https://github.com/EPMatt/awesome-ha-blueprints
```

## Activity corpora (manual)

- CASAS Twor: https://casas.wsu.edu/datasets/ -> datasets/casas_twor/
- CASAS Multi-resident ADL: same site -> datasets/casas_multi_adl/
- ARAS: https://www.cmpe.boun.edu.tr/aras/ -> datasets/aras_house_a/, aras_house_b/

Never commit dataset files.
