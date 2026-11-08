import sys
from pathlib import Path

SHOWCASE = Path(__file__).parents[1]
sys.path.insert(0, str(SHOWCASE))  # pages import theme / loaders the way Streamlit runs them
