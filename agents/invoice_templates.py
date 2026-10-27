def safe_money(val):
    """Return formatted money or N/A if the value is invalid."""
    try:
        return f"${float(val):.2f}"
    except Exception:
        return "N/A"


def safe_text(val):
    """Return text or N/A if None or empty."""
    return val if val not in (None, "", "None") else "N/A"


def get_invoice_html(data: dict, title: str = "Invoice Approval Required") -> str:
    """
    Generates an HTML email body for invoice approval.
    Fully safe: handles corrupted OCR values without crashing.
    """
    

    # ==========================
    #   GLOBAL FIELDS SAFE
    # ==========================
    vendor_name = safe_text(data.get("Vendor_Name"))
    invoice_number = safe_text(data.get("Invoice_No"))
    invoice_date = safe_text(data.get("Date"))

    severity = safe_text(data.get("severity"))
    confidence = safe_text(data.get("confidence"))


    anomaly_detected_date = safe_text(data.get("anomaly_detected_date"))

    # ==========================
    #   FINAL HTML TEMPLATE
    # ==========================
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 0; margin: 0; }}
            .container {{ max-width: 600px; margin: 20px auto; background: #fff; padding: 20px;
                          border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .header {{ background: #2c3e50; color: #fff; padding: 20px; text-align: center;
                       border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 22px; }}

            .alert-box {{ background-color: #f8d7da; color: #721c24; padding: 15px; border-radius: 4px;
                          margin: 20px 0; border: 1px solid #f5c6cb; }}

            .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
            .info-item {{ background: #f8f9fa; padding: 10px; border-radius: 4px; }}
            .info-label {{ font-weight: bold; color: #666; font-size: 12px; }}
            .info-value {{ font-size: 16px; margin-top: 4px; }}

            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ background: #f8f9fa; padding: 10px; font-size: 12px; border-bottom: 2px solid #ddd;
                 text-transform: uppercase; color: #666; }}

            .total-section {{ text-align: right; font-size: 18px; margin-top: 20px; }}

            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #888; }}

            .status-badge {{
                display: inline-block; padding: 4px 10px; border-radius: 12px; 
                font-size: 12px; font-weight: bold; background-color: #dc3545; color: white;
            }}
        </style>
    </head>

    <body>
        <div class="container">

            <!-- HEADER -->
            <div class="header">
                <h1>{title}</h1>
            </div>

            <!-- ANOMALY BOX -->
            <div class="alert-box">
                <div style="font-weight: bold; margin-bottom: 5px;">
                    ⚠️ Anomaly Detected: {safe_text(data.get("anomaly_one_line"))}
                </div>

                <div style="font-size: 14px;">
                    {safe_text(data.get("reason"))}
                </div>

                <div style="margin-top: 10px; font-size: 12px; border-top: 1px solid #eeb0b7; padding-top: 10px;">
                    <strong>Recommendation:</strong> {safe_text(data.get("recommendation"))}
                </div>
            </div>

            <!-- INFO GRID -->
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">VENDOR</span>
                    <span class="info-value">{data.get('Vendor_Name', 'N/A')}</span>
                </div>

                <div class="info-item">
                    <span class="info-label">INVOICE NO</span>
                    <span class="info-value">{data.get('Invoice_No', 'N/A')}</span>
                </div>

                <div class="info-item">
                    <span class="info-label">DATE</span>
                    <span class="info-value">{data.get('Date', 'N/A')}</span>
                </div>

                <div class="info-item">
                    <span class="info-label">SEVERITY / CONFIDENCE</span>
                    <span class="info-value">
                        <span class="status-badge">{severity}</span> {confidence}
                    </span>
                </div>
            </div>

            <!-- FOOTER -->
            <div class="footer">
                <p>Detected at: {anomaly_detected_date}</p>
                <p>Invoice Agent Automated System</p>
            </div>
        </div>
    </body>
    </html>
    """
