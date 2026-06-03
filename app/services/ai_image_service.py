"""AI service functions for image analysis (single and multi-image)."""

from app.services.key_manager import generate_content
from app.services.ai_prompts import (
    IMAGE_ANALYSIS_PROMPT,
    IMAGE_RECOMMENDATION_PROMPT,
    RESPONSE_LANGUAGE_INSTRUCTION,
)


def analyze_image(image_base64: str, user_text: str = "") -> str:
    """Analyzes a medication image and returns the identified product."""
    content_parts = [
        {"type": "text", "text": f"User message: {user_text}" if user_text else "Identify this medication."},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
        },
    ]

    try:
        result = generate_content(
            contents=content_parts,
            system_prompt=IMAGE_ANALYSIS_PROMPT,
            temperature=0.0,
            max_completion_tokens=100,
        )
    except Exception as e:
        print(f"[analyze_image error] {e}")
        return None
    if result is None:
        return None
    return result.strip().strip('"\'`')


MULTI_IMAGE_ANALYSIS_PROMPT = """You are a pharmaceutical image recognition assistant.
You are analyzing MULTIPLE images of medications at once.
For EACH image, identify the medication name, dosage, form, and laboratory/brand if visible.

Rules:
- Analyze EACH image independently and provide a structured identification for each.
- Respond with one line per image in this EXACT format:
  IMAGE 1: <drug name> | <dosage> | <form> | <laboratory>
  IMAGE 2: <drug name> | <dosage> | <form> | <laboratory>
  ...
- The drug name MUST be the generic/common name in English (e.g., "Acetaminophen" not "Acetaminofén", "Vitamin C" not "Vitamina C", "Ibuprofen" not "Ibuprofeno").
- For each image, provide a short structured identification like: "Ibuprofen | 400mg | tablets | Bayer"
- If you can partially identify the medication, still provide what you can.
- If an image clearly shows something unrelated to health/pharmacy, write: NOT_MEDICATION
- Do NOT skip any image. Provide a result for every single image.
"""


MULTI_IMAGE_RECOMMENDATION_PROMPT = """You are a friendly and knowledgeable pharmacy assistant.
A customer has shared MULTIPLE images of medications. You have analyzed all images and identified the products.
Below you have:
1. What was identified in each image
2. The user's message/question
3. Matching products available in our pharmacy for each identified medication

Rules:
- Start by confirming what you identified in the images (e.g., "I can see you have images of Ibuprofen 400mg, Vitamin C 500mg, and Acetaminophen 500mg...").
- For EACH identified medication, show the matching products from our pharmacy with details (name, dosage, form, price, laboratory).
- If a medication has MULTIPLE options (different labs/dosages), list ALL options numbered so the customer can choose.
- If a medication has only ONE option, show it directly.
- ALL prices are in Colombian Pesos (COP). Write prices as the number followed by COP. Do NOT use the $ symbol.
- Do NOT use markdown formatting like **bold**, *italic*, or special characters. Write in plain text only.
- Be warm and professional, like a pharmacist helping a customer.
- At the end, ask if they would like to order any or all of these medications.
- If some medications were not found, mention it clearly.
- Group the information by medication for clarity.
"""


def analyze_multiple_images(images_base64: list[str], user_text: str = "") -> list[str]:
    """Analyzes multiple medication images and returns a list of identified products.
    Each element corresponds to one image's identification result.
    """
    # Build content parts with all images
    content_parts = [
        {"type": "text", "text": f"User message: {user_text}\n\nAnalyze the following {len(images_base64)} images of medications:" if user_text else f"Identify the medications in the following {len(images_base64)} images:"},
    ]

    for i, img_b64 in enumerate(images_base64):
        content_parts.append({"type": "text", "text": f"Image {i + 1}:"})
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
        })

    try:
        result = generate_content(
            contents=content_parts,
            system_prompt=MULTI_IMAGE_ANALYSIS_PROMPT,
            temperature=0.0,
            max_completion_tokens=50 * len(images_base64),  # ~50 tokens per image
        )
    except Exception as e:
        print(f"[analyze_multiple_images error] {e}")
        return []

    if result is None:
        return []

    # Parse the response — expect "IMAGE N: <identification>" per line
    identifications = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("IMAGE"):
            # Extract the part after "IMAGE N:"
            parts = line.split(":", 1)
            if len(parts) > 1:
                identifications.append(parts[1].strip())
            else:
                identifications.append(line)
        elif line and not line.startswith("-"):
            # Fallback: if the model doesn't use the exact format
            identifications.append(line)

    return identifications


def generate_multi_image_recommendation(user_text: str, image_analyses: list[str], products_by_image: list[list[dict]], language: str = "es") -> str:
    """Generates a response combining multiple image analyses with product recommendations.
    
    Args:
        user_text: The user's message/question.
        image_analyses: List of identification strings, one per image.
        products_by_image: List of lists — for each image, the matching products found in DB.
        language: Language code for the response.
    """
    lang_instruction = {
        "en": "You MUST respond ENTIRELY in English.",
        "fr": "You MUST respond ENTIRELY in French.",
        "es": "You MUST respond ENTIRELY in Spanish.",
    }.get(language, "You MUST respond ENTIRELY in Spanish.")

    # Build the analysis + products text
    analysis_text = ""
    for i, analysis in enumerate(image_analyses):
        analysis_text += f"\nImage {i + 1} identified as: {analysis}\n"
        products = products_by_image[i] if i < len(products_by_image) else []
        if products:
            analysis_text += "  Matching products in our pharmacy:\n"
            for p in products:
                analysis_text += (
                    f"  - {p['name']} | Dosage: {p.get('medication_dosage', 'N/A')} | "
                    f"Form: {p.get('dosage_form', 'N/A')} | Lab: {p.get('laboratory', 'N/A')} | "
                    f"Price: {p.get('price', 'N/A')} COP | Stock: {p.get('actual_stock', 'N/A')} units\n"
                )
        else:
            analysis_text += "  No matching products found in our inventory.\n"

    user_message = (
        f"User message (RESPOND IN THIS LANGUAGE): {user_text}\n\n"
        f"Analysis results:\n{analysis_text}\n\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}"
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=MULTI_IMAGE_RECOMMENDATION_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
            max_completion_tokens=1000,
        )
    except Exception as e:
        return f"I identified the following medications: {', '.join(image_analyses)}. However, I encountered an error generating recommendations."
    if result is None:
        return f"I identified the following medications: {', '.join(image_analyses)}. Please try again for product recommendations."
    return result.strip()


def generate_image_recommendation(user_text: str, image_analysis: str, products_data: list[dict], language: str = "en") -> str:
    """Generates a response combining image analysis with product recommendations."""
    lang_instruction = {
        "en": "You MUST respond ENTIRELY in English.",
        "fr": "You MUST respond ENTIRELY in French.",
        "es": "You MUST respond ENTIRELY in Spanish.",
    }.get(language, "You MUST respond ENTIRELY in English.")

    if products_data:
        products_text = "\n".join(
            f"- {p['name']} | Dosage: {p.get('medication_dosage', 'N/A')} | Form: {p.get('dosage_form', 'N/A')} | "
            f"Lab: {p.get('laboratory', 'N/A')} | Price: {p.get('price', 'N/A')} COP | Stock: {p.get('actual_stock', 'N/A')} units"
            for p in products_data
        )
    else:
        products_text = "No matching products found in our current inventory."

    user_message = (
        f"Image analysis result: {image_analysis}\n\n"
        f"User message: {user_text}\n\n"
        f"Available matching products in our pharmacy:\n{products_text}\n\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}"
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=IMAGE_RECOMMENDATION_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
        )
    except Exception as e:
        return f"I identified the medication as: {image_analysis}. However, I encountered an error generating recommendations."
    if result is None:
        return f"I identified the medication as: {image_analysis}. Please try again for product recommendations."
    return result.strip()


