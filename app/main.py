from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import tempfile
import os

from utils.pipeline import run_full_pipeline
from utils.visualize_boxes import plot_boxes_3d
from utils.parse_xlsx import parse_pallet_excel

app = FastAPI(title="Pallet Optimizer")

# Hardcode container parameters for now
W, L, H = 235, 1203, 270
BUF = 5


@app.post("/optimize")
async def optimize_pallets(file: UploadFile = File(...)):
    """
    Upload an Excel file, run the full pipeline (Model A + B),
    and return a simple JSON summary.

    Later we can return images / files too.
    """
    # 1) Save uploaded file to a temp path
    suffix = os.path.splitext(file.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 2) Run the full pipeline on that temp Excel
        result = {}

        # Run placement
        lengths, widths, heights, pallets_data = parse_pallet_excel(tmp_path)
        from models.A_box_placement_model import BoxPlacementModel
        modelA = BoxPlacementModel(lengths, widths, heights, W, L, H, BUF)
        solvedA = modelA.solve(solver="ortools", time_limit=60)

        if not solvedA:
            return JSONResponse(
                status_code=400,
                content={"status": "no_solution", "detail": "Placement model failed"}
            )

        max_y = modelA.max_y_extent.value()
        free_len = max(0, L - max_y)

        result["placement"] = {
            "max_used_height": modelA.max_used_height.value(),
            "max_x_extent": modelA.max_x_extent.value(),
            "max_y_extent": modelA.max_y_extent.value(),
            "free_len_y": free_len,
        }

        # 3) Run recommendation model
        from models.B_reccomend_fill_model import ReccomendFillModel
        lengths_types = [p["length"] for p in pallets_data]
        widths_types  = [p["width"]  for p in pallets_data]
        heights_types = [p["height"] for p in pallets_data]

        max_add = [10] * len(pallets_data)
        modelB = ReccomendFillModel(lengths_types, widths_types, heights_types, BUF, free_len, max_add)
        solvedB = modelB.solve(solver="ortools", time_limit=60)

        if solvedB:
            add_list = modelB.get_solution_add()
            result["recommendation"] = {
                "add_per_type": add_list,
                "total_added_volume": modelB.total_added_volume.value(),
            }
        else:
            result["recommendation"] = {
                "status": "no_solution"
            }

        return result

    finally:
        # cleanup temp file
        os.remove(tmp_path)