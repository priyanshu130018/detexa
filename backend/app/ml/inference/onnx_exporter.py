"""
app/ml/inference/onnx_exporter.py
─────────────────────────────────────────────────────────────────────────────
Utilities to export trained XGBoost pipelines to ONNX format for accelerated inference.
"""

from pathlib import Path
from typing import Optional
from app.core.logging import logger


def export_pipeline_to_onnx(
    pipeline_obj,
    output_path: Optional[str] = None,
    num_features: int = 43,
) -> Optional[str]:
    """
    Exports a trained scikit-learn / XGBoost pipeline to ONNX format if onnxmltools/skl2onnx is present.
    """
    out_file = Path(output_path or "app/ml/saved/credit_fraud_model.onnx")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
        import onnx

        initial_type = [("float_input", FloatTensorType([None, num_features]))]
        onx = convert_sklearn(pipeline_obj, initial_types=initial_type, target_opset=15)
        with open(out_file, "wb") as f:
            f.write(onx.SerializeToString())
        logger.info(f"Successfully exported ONNX model to {out_file}")
        return str(out_file)
    except Exception as exc:
        logger.debug(f"ONNX export skipped (converter optional dependencies not present: {exc}).")
        return None
