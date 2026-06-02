"""
Email Service - AWS SES Integration.

Sends invoice PDFs as email attachments using Amazon Simple Email Service (SES).
"""

import os
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from botocore.exceptions import ClientError


def _get_ses_client():
    """Creates and returns a boto3 SES client.
    
    In AWS (ECS/EC2), uses IAM Role automatically (no keys needed).
    Locally, falls back to environment variables or ~/.aws/credentials.
    """
    region = os.getenv("AWS_REGION", "us-east-1")
    
    # If explicit keys are set (local development), use them
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if access_key and secret_key:
        return boto3.client(
            "ses",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
    
    # In AWS, boto3 automatically uses the IAM Role attached to the task/instance
    return boto3.client("ses", region_name=region)


def send_invoice_email(
    recipient_email: str,
    customer_name: str,
    pdf_bytes: bytes,
    pdf_filename: str,
    order_summary: dict,
    language: str = "es",
) -> dict:
    """
    Sends an invoice PDF via email using AWS SES.

    Args:
        recipient_email: Customer's email address.
        customer_name: Customer's full name.
        pdf_bytes: The generated PDF invoice as bytes.
        pdf_filename: Filename for the PDF attachment.
        order_summary: Dict with keys: product, quantity, total.
        language: Language code for the email body ('es', 'en', 'fr').

    Returns:
        dict with 'success' (bool) and 'message' (str) or 'error' (str).
    """
    sender_email = os.getenv("SES_SENDER_EMAIL")
    if not sender_email:
        return {"success": False, "error": "SES_SENDER_EMAIL not configured."}

    # Build email subject and body based on language
    subject, body_html, body_text = _build_email_content(
        customer_name, order_summary, language
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
        print(f"[email_service] Invoice sent to {recipient_email} (MessageId: {message_id})")
        return {"success": True, "message": f"Email sent successfully (ID: {message_id})"}
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        print(f"[email_service] SES error: {error_code} - {error_message}")
        return {"success": False, "error": f"{error_code}: {error_message}"}
    except Exception as e:
        print(f"[email_service] Unexpected error: {e}")
        return {"success": False, "error": str(e)}


def _build_email_content(
    customer_name: str, order_summary: dict, language: str
) -> tuple[str, str, str]:
    """
    Builds the email subject, HTML body, and plain text body.

    Returns:
        Tuple of (subject, body_html, body_text).
    """
    product = order_summary.get("product", "N/A")
    quantity = order_summary.get("quantity", 1)
    total = order_summary.get("total", 0)

    if language == "en":
        subject = "AI Explorer Pharmacy - Your Invoice"
        body_text = (
            f"Hello {customer_name},\n\n"
            f"Thank you for your purchase at AI Explorer Pharmacy.\n\n"
            f"Order summary:\n"
            f"- Product: {product}\n"
            f"- Quantity: {quantity}\n"
            f"- Total: {total:,.2f} COP\n\n"
            f"Your invoice is attached as a PDF.\n\n"
            f"If you have any questions, feel free to contact us.\n\n"
            f"Best regards,\n"
            f"AI Explorer Pharmacy"
        )
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #21618C, #2E86C1); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">AI Explorer Pharmacy</h1>
                <p style="color: #D6EAF8; margin: 5px 0 0 0;">Your trusted pharmacy</p>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border: 1px solid #e0e0e0;">
                <p>Hello <strong>{customer_name}</strong>,</p>
                <p>Thank you for your purchase. Here is your order summary:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background: #21618C; color: white;">
                        <th style="padding: 10px; text-align: left;">Product</th>
                        <th style="padding: 10px; text-align: center;">Quantity</th>
                        <th style="padding: 10px; text-align: right;">Total</th>
                    </tr>
                    <tr style="background: white;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{product}</td>
                        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #eee;">{quantity}</td>
                        <td style="padding: 10px; text-align: right; border-bottom: 1px solid #eee;">{total:,.2f} COP</td>
                    </tr>
                </table>
                <p>Your invoice is attached as a PDF file.</p>
                <p>If you have any questions, feel free to contact us.</p>
            </div>
            <div style="padding: 15px; text-align: center; color: #888; font-size: 12px;">
                <p>AI Explorer Pharmacy - Your trusted pharmacy</p>
            </div>
        </body>
        </html>
        """

    elif language == "fr":
        subject = "AI Explorer Pharmacy - Votre Facture"
        body_text = (
            f"Bonjour {customer_name},\n\n"
            f"Merci pour votre achat chez AI Explorer Pharmacy.\n\n"
            f"Resume de la commande:\n"
            f"- Produit: {product}\n"
            f"- Quantite: {quantity}\n"
            f"- Total: {total:,.2f} COP\n\n"
            f"Votre facture est jointe en PDF.\n\n"
            f"Si vous avez des questions, n'hesitez pas a nous contacter.\n\n"
            f"Cordialement,\n"
            f"AI Explorer Pharmacy"
        )
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #21618C, #2E86C1); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">AI Explorer Pharmacy</h1>
                <p style="color: #D6EAF8; margin: 5px 0 0 0;">Votre pharmacie de confiance</p>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border: 1px solid #e0e0e0;">
                <p>Bonjour <strong>{customer_name}</strong>,</p>
                <p>Merci pour votre achat. Voici le resume de votre commande:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background: #21618C; color: white;">
                        <th style="padding: 10px; text-align: left;">Produit</th>
                        <th style="padding: 10px; text-align: center;">Quantite</th>
                        <th style="padding: 10px; text-align: right;">Total</th>
                    </tr>
                    <tr style="background: white;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{product}</td>
                        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #eee;">{quantity}</td>
                        <td style="padding: 10px; text-align: right; border-bottom: 1px solid #eee;">{total:,.2f} COP</td>
                    </tr>
                </table>
                <p>Votre facture est jointe en fichier PDF.</p>
                <p>Si vous avez des questions, n'hesitez pas a nous contacter.</p>
            </div>
            <div style="padding: 15px; text-align: center; color: #888; font-size: 12px;">
                <p>AI Explorer Pharmacy - Votre pharmacie de confiance</p>
            </div>
        </body>
        </html>
        """

    else:  # Spanish (default)
        subject = "AI Explorer Pharmacy - Tu Factura"
        body_text = (
            f"Hola {customer_name},\n\n"
            f"Gracias por tu compra en AI Explorer Pharmacy.\n\n"
            f"Resumen del pedido:\n"
            f"- Producto: {product}\n"
            f"- Cantidad: {quantity}\n"
            f"- Total: {total:,.2f} COP\n\n"
            f"Tu factura esta adjunta en formato PDF.\n\n"
            f"Si tienes alguna pregunta, no dudes en contactarnos.\n\n"
            f"Saludos cordiales,\n"
            f"AI Explorer Pharmacy"
        )
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #21618C, #2E86C1); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">AI Explorer Pharmacy</h1>
                <p style="color: #D6EAF8; margin: 5px 0 0 0;">Tu farmacia de confianza</p>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border: 1px solid #e0e0e0;">
                <p>Hola <strong>{customer_name}</strong>,</p>
                <p>Gracias por tu compra. Aqui tienes el resumen de tu pedido:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background: #21618C; color: white;">
                        <th style="padding: 10px; text-align: left;">Producto</th>
                        <th style="padding: 10px; text-align: center;">Cantidad</th>
                        <th style="padding: 10px; text-align: right;">Total</th>
                    </tr>
                    <tr style="background: white;">
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{product}</td>
                        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #eee;">{quantity}</td>
                        <td style="padding: 10px; text-align: right; border-bottom: 1px solid #eee;">{total:,.2f} COP</td>
                    </tr>
                </table>
                <p>Tu factura esta adjunta como archivo PDF.</p>
                <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
            </div>
            <div style="padding: 15px; text-align: center; color: #888; font-size: 12px;">
                <p>AI Explorer Pharmacy - Tu farmacia de confianza</p>
            </div>
        </body>
        </html>
        """

    return subject, body_html, body_text
