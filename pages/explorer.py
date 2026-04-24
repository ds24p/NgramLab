from shiny import render, ui


def explorer_ui():
    return ui.div(
        ui.div("Explorer", class_="page-title"),
        ui.p(
            "This page will display interactive word trajectories over time.",
            class_="muted"
        ),
        ui.input_select("selected_word", "Choose word", choices=[]),
        ui.output_plot("trajectory_plot"),
        class_="card"
    )


def explorer_server(input, output, session, shared):

    @output
    @render.plot
    def trajectory_plot():
        import matplotlib.pyplot as plt

        df = shared["uploaded_df"]
        years = shared["uploaded_years"]
        word = input.selected_word()

        fig, ax = plt.subplots(figsize=(8, 4.5))

        if df is None or not years or not word:
            ax.text(0.5, 0.5, "Upload a file and choose a word", ha="center", va="center")
            ax.set_axis_off()
            return fig

        row = df[df["word"] == word]

        if row.empty:
            ax.text(0.5, 0.5, "Word not found", ha="center", va="center")
            ax.set_axis_off()
            return fig

        values = row.iloc[0][years].to_numpy(dtype=float)

        ax.plot(years, values, marker="o")
        ax.set_title(f"Trajectory: {word}")
        ax.set_xlabel("Year")
        ax.set_ylabel("Frequency")
        ax.grid(True, alpha=0.25)

        return fig