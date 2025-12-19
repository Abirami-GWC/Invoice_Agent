from app.workflow import workflow

def draw_graph():
    graph = workflow.get_graph()

    png_bytes = graph.draw_mermaid_png()

    with open("invoice_workflow.png", "wb") as f:
        f.write(png_bytes)

    print("Invoice workflow graph saved as invoice_workflow.png")

if __name__ == "__main__":
    draw_graph()
