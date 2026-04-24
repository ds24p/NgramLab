from shiny import reactive, render, ui
import pandas as pd
import numpy as np

from utils import auc_trapezoid


def auc_lab_ui():
    return ui.div(
        ui.div("AUC Lab", class_="page-title"),
        ui.p(
            "This page will compute area under the curve for selected words or full datasets.",
            class_="muted"
        ),
        ui.input_checkbox("exclude_zero_years", "Exclude zero years", value=False),
        ui.input_action_button("compute_auc", "Compute AUC"),
        ui.output_data_frame("auc_table"),
        class_="card"
    )


def auc_lab_server(input, output, session, shared):

    @output
    @render.data_frame
    @reactive.event(input.compute_auc)
    def auc_table():
        df = shared["uploaded_df"]
        years = shared["uploaded_years"]

        if df is None or not years:
            return render.DataGrid(pd.DataFrame({"message": ["Upload a file first."]}))

        rows = []

        for _, row in df.iterrows():
            values = row[years].to_numpy(dtype=float)

            if input.exclude_zero_years():
                valid_mask = np.isfinite(values) & (values != 0)
                auc_years = np.asarray(years)[valid_mask].tolist()
                auc_values = values[valid_mask]
            else:
                auc_years = years
                auc_values = values

            if len(auc_years) < 2:
                auc_value = np.nan
            else:
                auc_value = auc_trapezoid(auc_years, auc_values)

            rows.append({
                "word": row["word"],
                "auc": auc_value,
                "n_years_used": len(auc_years),
            })

        result = pd.DataFrame(rows).sort_values(
            "auc",
            ascending=False,
            na_position="last"
        )

        return render.DataGrid(result)