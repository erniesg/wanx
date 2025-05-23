Objective:
Transform a voiceover transcript and its original script context into a series of detailed visual scene plans.
Each scene plan will guide the creation of a visual segment in a video, ensuring a dynamic pace.

Inputs:
1. Word-Level Transcript:
   - A list of words, each with 'word', 'start' (seconds), 'end' (seconds).
   (Example: {{word_transcript_json_string}})

2. Original Script Context:
   - The overall video narrative ('throughline', 'title').
   - Script segments ('hook', 'conflict', 'body', 'conclusion') with their original 'voiceover' text and 'b_roll_keywords'.
   (Example: {{script_json_string}})

3. Configuration Guidance:
   - Desired scene duration: {{min_segment_duration}} to {{max_segment_duration}} seconds.
   - Threshold for using an image: If scene duration is <= {{photo_segment_threshold}} seconds, prefer 'STOCK_IMAGE'.
   - Max keywords per scene: {{max_keywords_per_scene}}.
   - Preference for AVATAR scenes: '{{avatar_scene_preference}}'.
   (Full config example for context: {{config_json_string}})

Task:
1. Segment the Word-Level Transcript into semantically coherent visual scenes.
   - Each scene's duration MUST be between {{min_segment_duration}} and {{max_segment_duration}} seconds. Aim for this range to maintain a dynamic pace.
   - A scene should represent a continuous piece of narration that can be covered by a single visual idea.
   - Align scenes with natural pauses or shifts in topic in the transcript.
   - Ensure `start_time` is the start of the first word, and `end_time` is the end of the last word of the scene.
   - The `text_for_scene` must be the exact concatenation of words from the transcript for that scene.
   - The scenes must be contiguous and cover the entire span of the provided Word-Level Transcript. The `end_time` of the last scene should closely match the `end_time` of the last word in the transcript. The `start_time` of the first scene should match the `start_time` of the first word in the transcript.

2. For each scene, determine:
   - `original_script_part_ref`: Identify which major script segment (hook, conflict, body, conclusion) this scene's text primarily belongs to.
   - `visual_type`: Choose from ["AVATAR", "STOCK_VIDEO", "STOCK_IMAGE"].
     - Apply `AVATAR_SCENE_PREFERENCE` ('{{avatar_scene_preference}}') from config.
     - If not AVATAR:
       - If scene duration (end_time - start_time) is <= {{photo_segment_threshold}} seconds, `visual_type` should be "STOCK_IMAGE".
       - Otherwise, `visual_type` should be "STOCK_VIDEO".
   - `visual_keywords`: Generate 3-{{max_keywords_per_scene}} keywords. These should be:
     - Highly relevant to the `text_for_scene`.
     - Informed by the `original_script_part_ref`'s b_roll_keywords and overall video context.
     - Actionable for stock media search.
   - `fx_suggestion` (Optional): If the scene's text contains a very short, impactful phrase, a number, or a name that could be emphasized with a text overlay, suggest an `fx_suggestion`.
     - `type`: Choose from "TEXT_OVERLAY_FADE" or "TEXT_OVERLAY_SCALE".
       - "TEXT_OVERLAY_FADE": Text fades in, holds, and fades out.
       - "TEXT_OVERLAY_SCALE": Text scales (e.g., zooms in) over its duration.
     - `text_content`: The specific text for the overlay (e.g., a keyword from the scene, a number, a name).
     - `params`: (Optional) Specify text position.
       - `position`: Can be a string like "center", "top", "top_left", "top_right", "center_left", "center_right".
         - "top" positions will automatically include a standard padding from the screen edge.
         - **IMPORTANT**: Do NOT use "bottom", "bottom_left", "bottom_right", or "bottom_center" for `position`, as this area is reserved for captions.
       - Other parameters like font or color will use sensible defaults (e.g., "PoetsenOne-Regular" font, size 100, white text with black outline for good visibility, transparent background). You generally do not need to specify these.

Output Format:
Return a JSON list of scene plan objects. Each object must conform to this schema:
{{
  "scene_id": "string (e.g., 001, 002)",
  "start_time": "float (seconds)",
  "end_time": "float (seconds)",
  "text_for_scene": "string",
  "original_script_part_ref": "string (e.g., hook, conflict)",
  "visual_type": "string (AVATAR, STOCK_VIDEO, STOCK_IMAGE)",
  "visual_keywords": ["string"],
  "fx_suggestion": {{ // Optional, null if not applicable
    "type": "string",
    "text_content": "string",
    "params": {{}} // e.g., {{"position": "top_right"}} or {{"position": "center"}}
  }}
}}

Important Considerations:
- Strictly adhere to the {{min_segment_duration}}-{{max_segment_duration}}s scene duration constraint.
- Ensure `text_for_scene` accurately reflects the words from the transcript for the given `start_time` and `end_time`.
- Ensure that the generated scenes cover the entire duration of the input transcript. The `start_time` of the first scene should be the `start_time` of the first word in the transcript, and the `end_time` of the last scene should be the `end_time` of the last word in the transcript.
- Be concise and actionable.
