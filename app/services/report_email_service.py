"""
Report Email Service - AWS SES Integration.

Sends data report PDFs (charts, tables, summaries) as email attachments
using Amazon Simple Email Service (SES).
"""

import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from botocore.exceptions import ClientError

from app.services.email_service import _get_ses_client


def send_report_email(
    recipient_email: str,
    recipient_name: str,
    pdf_bytes: bytes,
    pdf_filename: str,
    report_summary: dict,
    language: str = "es",
) -> dict:
    """
    Sends a data report PDF via email using AWS SES.

    Args:
        recipient_email: Recipient's email address.
        recipient_name: Recipient's name (or 'User').
        pdf_bytes: The generated report PDF as bytes.
        pdf_filename: Filename for the PDF attachment.
        report_summary: Dict with keys: query, summary, row_count, chart_type.
        language: Language code for the email body ('es', 'en', 'fr').

    Returns:
        dict with 'success' (bool) and 'message' (str) or 'error' (str).
    """
    sender_email = os.getenv("SES_SENDER_EMAIL")
    if not sender_email:
        return {"success": False, "error": "SES_SENDER_EMAIL not configured."}

    # Build email content
    subject, body_html, body_text = _build_report_email_content(
        recipient_name, report_summary, language
    )

    # Create MIME message
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    # Email body (HTML + plain text fallback)
    msg_body = MIMEMultipart("alternative")
    msg_body.attach(MIMEText(body_text, "plain", "utf-8"))
    msg_body.attach(MIMEText(body_html, "html", "utf-8"))
    msg.attach(msg_body)

    # PDF attachment
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=pdf_filename
    )
    msg.attach(attachment)

    # Send via SES
    try:
        client = _get_ses_client()
        response = client.send_raw_email(
            Source=sender_email,
            Destinations=[recipient_email],
            RawMessage={"Data": msg.as_string()},
        )
        message_id = response.get("MessageId", "unknown")
        print(f"[report_email_service] Report sent to {recipient_email} (MessageId: {message_id})")
        return {"success": True, "message": f"Email sent successfully (ID: {message_id})"}
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        print(f"[report_email_service] SES error: {error_code} - {error_message}")
        return {"success": False, "error": f"{error_code}: {error_message}"}
    except Exception as e:
        print(f"[report_email_service] Unexpected error: {e}")
        return {"success": False, "error": str(e)}


def _build_report_email_content(
    recipient_name: str, report_summary: dict, language: str
) -> tuple[str, str, str]:
    """
    Builds the report email subject, HTML body, and plain text body.

    Returns:
        Tuple of (subject, body_html, body_text).
    """
    query = report_summary.get("query", "N/A")
    summary = report_summary.get("summary", "")
    row_count = report_summary.get("row_count", 0)
    chart_type = report_summary.get("chart_type", "NONE")

    chart_label = {
        "BAR": "bar chart / grafico de barras",
        "LINE": "line chart / grafico de lineas",
        "PIE": "pie chart / grafico circular",
        "NONE": "",
    }.get(chart_type, "")

    if language == "en":
        subject = "AI Explorer Pharmacy - Your Data Report"
        body_text = (
            f"Hello {recipient_name},\n\n"
            f"Here is the data report you requested from AI Explorer Pharmacy.\n\n"
            f"Query: {query}\n"
            f"Results: {row_count} row(s)\n"
            f"{f'Chart type: {chart_label}' if chart_label else ''}\n\n"
            f"Summary: {summary}\n\n"
            f"The full report is attached as a PDF.\n\n"
            f"Best regards,\n"
            f"AI Explorer Pharmacy"
        )
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #21618C, #2E86C1); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">AI Explorer Pharmacy</h1>
                <p style="color: #D6EAF8; margin: 5px 0 0 0;">Your Data Report</p>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border: 1px solid #e0e0e0;">
                <p>Hello <strong>{recipient_name}</strong>,</p>
                <p>Here is the data report you requested:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background: #21618C; color: white;">
                        <th style="padding: 10px; text-align: left;">Detail</th>
                        <th style="padding: 10px; text-align: left;">Value</th>
                    </tr>
                    <tr style="background: white;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">Query</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{query[:100]}</td>
                    </tr>
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">Results</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{row_count} row(s)</td>
                    </tr>
                    {f'<tr style="background: white;"><td style="padding: 10px; border-bottom: 1px solid #eee;">Chart</td><td style="padding: 10px; border-bottom: 1px solid #eee;">{chart_label}</td></tr>' if chart_label else ''}
                </table>
                <p><strong>Summary:</strong> {summary[:300]}</p>
                <p>The full report with data table{' and chart' if chart_label else ''} is attached as a PDF.</p>
            </div>
            <div style="padding: 15px; text-align: center; color: #888; font-size: 12px;">
                <p>AI Explorer Pharmacy - Your trusted pharmacy</p>
            </div>
        </body>
        </html>
        """

    elif language == "fr":
        subject = "AI Explorer Pharmacy - Votre Rapport de Donnees"
        body_text = (
            f"Bonjour {recipient_name},\n\n"
            f"Voici le rapport de donnees que vous avez demande a AI Explorer Pharmacy.\n\n"
            f"Requete: {query}\n"
            f"Resultats: {row_count} ligne(s)\n"
            f"{f'Type de graphique: {chart_label}' if chart_label else ''}\n\n"
            f"Resume: {summary}\n\n"
            f"Le rapport complet est joint en PDF.\n\n"
            f"Cordialement,\n"
            f"AI Explorer Pharmacy"
        )
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #21618C, #2E86C1); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">AI Explorer Pharmacy</h1>
                <p style="color: #D6EAF8; margin: 5px 0 0 0;">Votre Rapport de Donnees</p>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border: 1px solid #e0e0e0;">
                <p>Bonjour <strong>{recipient_name}</strong>,</p>
                <p>Voici le rapport de donnees que vous avez demande:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background: #21618C; color: white;">
                        <th style="padding: 10px; text-align: left;">Detail</th>
                        <th style="padding: 10px; text-align: left;">Valeur</th>
                    </tr>
                    <tr style="background: white;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">Requete</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{query[:100]}</td>
                    </tr>
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">Resultats</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{row_count} ligne(s)</td>
                    </tr>
                    {f'<tr style="background: white;"><td style="padding: 10px; border-bottom: 1px solid #eee;">Graphique</td><td style="padding: 10px; border-bottom: 1px solid #eee;">{chart_label}</td></tr>' if chart_label else ''}
                </table>
                <p><strong>Resume:</strong> {summary[:300]}</p>
                <p>Le rapport complet avec tableau{' et graphique' if chart_label else ''} est joint en PDF.</p>
            </div>
            <div style="padding: 15px; text-align: center; color: #888; font-size: 12px;">
                <p>AI Explorer Pharmacy - Votre pharmacie de confiance</p>
            </div>
        </body>
        </html>
        """

    else:  # Spanish (default)
        subject = "AI Explorer Pharmacy - Tu Reporte de Datos"
        body_text = (
            f"Hola {recipient_name},\n\n"
            f"Aqui tienes el reporte de datos que solicitaste desde AI Explorer Pharmacy.\n\n"
            f"Consulta: {query}\n"
            f"Resultados: {row_count} fila(s)\n"
            f"{f'Tipo de grafico: {chart_label}' if chart_label else ''}\n\n"
            f"Resumen: {summary}\n\n"
            f"El reporte completo esta adjunto en formato PDF.\n\n"
            f"Saludos cordiales,\n"
            f"AI Explorer Pharmacy"
        )
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #21618C, #2E86C1); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">AI Explorer Pharmacy</h1>
                <p style="color: #D6EAF8; margin: 5px 0 0 0;">Tu Reporte de Datos</p>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border: 1px solid #e0e0e0;">
                <p>Hola <strong>{recipient_name}</strong>,</p>
                <p>Aqui tienes el reporte de datos que solicitaste:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background: #21618C; color: white;">
                        <th style="padding: 10px; text-align: left;">Detalle</th>
                        <th style="padding: 10px; text-align: left;">Valor</th>
                    </tr>
                    <tr style="background: white;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">Consulta</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{query[:100]}</td>
                    </tr>
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">Resultados</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{row_count} fila(s)</td>
                    </tr>
                    {f'<tr style="background: white;"><td style="padding: 10px; border-bottom: 1px solid #eee;">Grafico</td><td style="padding: 10px; border-bottom: 1px solid #eee;">{chart_label}</td></tr>' if chart_label else ''}
                </table>
                <p><strong>Resumen:</strong> {summary[:300]}</p>
                <p>El reporte completo con tabla de datos{' y grafico' if chart_label else ''} esta adjunto en PDF.</p>
            </div>
            <div style="padding: 15px; text-align: center; color: #888; font-size: 12px;">
                <p>AI Explorer Pharmacy - Tu farmacia de confianza</p>
            </div>
        </body>
        </html>
        """

    return subject, body_html, body_text
