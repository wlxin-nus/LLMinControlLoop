import os
import json
import logging
from typing import Optional

# Correctly import from the 'src' package
from .config import OPENAI_API_KEY, INPUT_DATA_DIR, OUTPUT_DATA_DIR
from .data_models import StaticBuildingData

from llama_index.core import SimpleDirectoryReader
from llama_index.program.openai import OpenAIPydanticProgram
from llama_index.llms.openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def run_extraction_pipeline():
    """
    Executes the complete information extraction pipeline.
    This version uses a highly optimized prompt with a few-shot example to ensure
    robust and accurate extraction of tabular data from Markdown files.
    """
    logging.info("--- Starting Static Building Information Extraction (V3 - Hardened Schema & Prompt) ---")

    # 1. Initialize the OpenAI LLM
    logging.info("Initializing OpenAI LLM (gpt-4o)...")
    llm = OpenAI(
        model="gpt-4o",
        api_key=OPENAI_API_KEY,
        temperature=0.0,  # Set to 0.0 for maximum determinism and accuracy
        request_timeout=180.0
    )

    # 2. Load documents from the input directory
    logging.info(f"Loading documents from directory: {INPUT_DATA_DIR}")
    try:
        reader = SimpleDirectoryReader(input_dir=INPUT_DATA_DIR, required_exts=[".md"])
        documents = reader.load_data()
        if not documents:
            logging.error(f"No '.md' documents found in {INPUT_DATA_DIR}. The pipeline will stop.")
            return
        # Combine all document texts into a single context string
        full_text = "\n\n---\n\n".join([doc.get_content() for doc in documents])
        logging.info(f"Successfully loaded and combined {len(documents)} document(s).")
    except Exception as e:
        logging.error(f"Fatal error during document loading: {e}", exc_info=True)
        return

    # 3. Create the Pydantic Program with the final, most robust prompt
    # --- [KEY IMPROVEMENT V3] ---
    # The example now shows the full nested structure (`building_info.envelope.roof`),
    # giving the LLM an unambiguous template to follow for all tables.
    prompt_template_str = (
        "You are a world-class AI expert in parsing technical building specifications. "
        "Your sole task is to extract information from the provided text in Markdown format and "
        "populate a JSON object that strictly adheres to the given Pydantic schema. "
        "You must be meticulous and precise.\n\n"

        "**MANDATORY RULES:**\n\n"

        "**1. ABSOLUTE SCHEMA ADHERENCE:** The final output MUST be a single, valid JSON object conforming to the "
        "`StaticBuildingData` schema. Do NOT include any other text, explanations, or markdown formatting like ```json. "
        "Your response must start with `{` and end with `}`.\n\n"

        "**2. RIGOROUS TABLE PARSING LOGIC:** The document contains critical data in Markdown tables. "
        "When you encounter a table describing material layers (e.g., for 'exterior_walls', 'roof', 'floors'), "
        "you MUST follow this procedure exactly:\n"
        "   a. For **EACH and EVERY data row** in the table, create a corresponding JSON object based on the `Layer` schema.\n"
        "   b. Group all these `Layer` objects into a single list under the `layers` key.\n"
        "   c. This list must be part of a **SINGLE** parent object (e.g., `exterior_walls`, `roof`). **DO NOT** create a new parent object for each row.\n"
        "   d. **DO NOT** leave numerical fields as `null` if a value (even 0) is present in the table. This is a critical requirement.\n\n"

        "   **--- BEGIN EXAMPLE ---**\n"
        "   IF the input document contains this section:\n"
        "   ```markdown\n"
        "   #### Roof Construction\n"
        "   The roof is a flat assembly with the following layers from outside to inside:\n\n"
        "   | Layer Name              | Thickness [m] | Thermal Conductivity [W/m-K] | Density [kg/m3] | Specific Heat Capacity [J/kg-K] |\n"
        "   |-------------------------|---------------|--------------------------------|-----------------|---------------------------------|\n"
        "   | Waterproofing Membrane  | 0.01          | 0.23                           | 1100            | 1700                            |\n"
        "   | Rigid Insulation        | 0.15          | 0.025                          | 30              | 1400                            |\n"
        "   | Concrete Deck           | 0.20          | 2.1                            | 2400            | 880                             |\n"
        "   | Gypsum Board            | 0.012         | 0.16                           | 700             | 1090                            |\n"
        "   ```\n\n"
        "   THEN your JSON output for the `building_info.envelope` section MUST be structured exactly like this:\n"
        "   ```json\n"
        "     \"building_info\": {\n"
        "       \"envelope\": {\n"
        "         \"roof\": {\n"
        "           \"layers\": [\n"
        "             {\n"
        "               \"name\": \"Waterproofing Membrane\",\n"
        "               \"thickness_m\": 0.01,\n"
        "               \"thermal_conductivity_W_mK\": 0.23,\n"
        "               \"density_kg_m3\": 1100.0,\n"
        "               \"specific_heat_capacity_J_kgK\": 1700.0\n"
        "             },\n"
        "             {\n"
        "               \"name\": \"Rigid Insulation\",\n"
        "               \"thickness_m\": 0.15,\n"
        "               \"thermal_conductivity_W_mK\": 0.025,\n"
        "               \"density_kg_m3\": 30.0,\n"
        "               \"specific_heat_capacity_J_kgK\": 1400.0\n"
        "             },\n"
        "             {\n"
        "               \"name\": \"Concrete Deck\",\n"
        "               \"thickness_m\": 0.20,\n"
        "               \"thermal_conductivity_W_mK\": 2.1,\n"
        "               \"density_kg_m3\": 2400.0,\n"
        "               \"specific_heat_capacity_J_kgK\": 880.0\n"
        "             },\n"
        "             {\n"
        "               \"name\": \"Gypsum Board\",\n"
        "               \"thickness_m\": 0.012,\n"
        "               \"thermal_conductivity_W_mK\": 0.16,\n"
        "               \"density_kg_m3\": 700.0,\n"
        "               \"specific_heat_capacity_J_kgK\": 1090.0\n"
        "             }\n"
        "           ]\n"
        "         }\n"
        "       }\n"
        "     }\n"
        "   ```\n"
        "   **--- END EXAMPLE ---**\n\n"

        "**3. BE THOROUGH:** Scour the entire document for every detail that fits the schema. Do not stop after finding only a few pieces of information.\n\n"

        "Now, analyze the following document and generate the complete JSON object.\n"
        "--- Document Text Begins ---\n"
        "{input}\n"
        "--- Document Text Ends ---"
    )

    program = OpenAIPydanticProgram.from_defaults(
        output_cls=StaticBuildingData,
        llm=llm,
        prompt_template_str=prompt_template_str,
        verbose=True  # Keep verbose=True to see the LLM interaction during debugging
    )

    # 4. Execute the extraction program
    logging.info("--- Calling Pydantic Program with the advanced prompt ---")
    final_data: Optional[StaticBuildingData] = None
    try:
        final_data = program(input=full_text)
        logging.info("Successfully received and parsed a valid response from the LLM.")
    except Exception as e:
        # This will catch errors during the program call, including parsing failures or API issues
        logging.error(f"The program call failed during execution: {e}", exc_info=True)
        logging.error(
            "This could be due to an LLM error, a malformed response that Pydantic couldn't parse, or a network issue. "
            "Check the logs above for the raw LLM output if available."
        )
        return

    # 5. Save the output to a JSON file
    if final_data:
        output_file_path = os.path.join(OUTPUT_DATA_DIR, "static_building_info.json")
        try:
            # Use model_dump_json for direct, Pydantic-native serialization
            with open(output_file_path, 'w', encoding='utf-8') as f:
                # The `indent=4` argument makes the JSON file human-readable
                json_string = final_data.model_dump_json(indent=4)
                f.write(json_string)
            logging.info(f"Successfully saved the extracted data to: {output_file_path}")
        except Exception as e:
            logging.error(f"Error while saving the JSON file: {e}", exc_info=True)
    else:
        logging.warning("Extraction resulted in empty or invalid data. No output file was generated.")

    logging.info("--- Static Building Information Extraction Pipeline Finished ---")
