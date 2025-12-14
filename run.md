brew install libomp

pip uninstall -y lightgbm
pip install --no-cache-dir lightgbm

stockreco fetch

stockreco build-features

python -c "import pandas as pd; from stockreco.config.settings import settings; from stockreco.models.expand_model import train_expand_lgbm; \
feat=pd.read_parquet(settings.data_dir/'features.parquet'); \
meta=train_expand_lgbm(feat, asof='2025-12-09', model_dir=settings.models_dir/'2025-12-09', thr=0.012); \
print(meta)"

stockreco recommend-both 2025-12-10 --aggressive-max-trades 2
