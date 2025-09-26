from pydantic import Field, MongoDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    MODE: str = Field(default="DEV")

    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_NAME: str

    S3_ENDPOINT: str
    S3_ACCESS_KEY: SecretStr
    S3_SECRET_KEY: SecretStr
    S3_BUCKET: str
    S3_FOLDER: str

    REDIS_DSN: RedisDsn

    CHUNK: int = Field(default=4096)

    DRIVER: str
    AD_BLOCK: str

    SITE_NAME: str

    G_SPREADSHEET_ID: str
    G_SPREADSHEET_MAIN_TAB: str = "Main"
    G_SPREADSHEET_PORNOLAB_TAB: str = "Pornolab Data"
    G_SPREADSHEET_TAB_PROMPT: str = "Grok Prompt Test"
    G_SPREADSHEET_CREDS: str

    GROK_API_KEY: str
    PROMPT_DEFAULT: str = """I need you to help me rewrite video titles for JAV movies. 
    After this message, I will only send you the titles I want rewritten. 
    For each input, rewrite the title into one creative, realistic, and 
    human-like video tube title that follows these rules exactly:

Rules
0. Important: Research porn and JAV sites and implement their lingo.
1. Start with the video code in square brackets. Example: [INCT-001].
2. Include 1–2 performer names from the provided list. If more names are given, choose the best fit.
3. Select 1–2 relevant tags and integrate them naturally.
4. Only use tags exactly as provided. Do not invent, reinterpret, or guess.
5. Skip vague/awkward tags (e.g., “Other fetish”) unless they sound natural.
6. Use minimal connectors only (“and”, “&”, “with”, “in”, “vs”, “x”).
7. Rephrase the title uniquely. Do not copy the original wording.
8. Keep total length 50–60 characters (including code). Small overflow is acceptable if needed for natural flow.
9. If under 50 characters, add another tag or performer (joined with “&”).
10. Title must be one smooth, logical phrase. No keyword stacking. 
No awkward endings. Keep this rule in mind at all times.
11. Provide exactly one rewritten title per input.
12. Exclude non-consensual or illegal themes. “Step” is allowed, but “incest” and similar are not.
13. Avoid bland or generic terms (“bliss”, “lust”, “passion”, “action”). Use concrete, descriptive wording.
14. Explicit, vulgar, and porn-appropriate language is permitted.
15. Do not use verbs as nouns/adjectives (e.g., “in a group fuck” = wrong). 
The title should include only descriptive and 
direct language and actual reflections of what's happening in the 
video based on researched context from the internet and provided input.
16. Vary word choice to avoid repetition across titles.
17. Do not combine multiple terms with the same meaning (e.g., “3P” and “Threesome” together).
18. Do not combine body parts with acts in unnatural ways (e.g., “Shaved Creampie”). 
Attribute tags correctly (e.g., “Shaved Ichigo Aoi”).
19. Adjectives may precede performer names (e.g., “Shaved Ichigo Aoi”).
20. Do not use contradicting tags (e.g., “3P & Solowork”).
21. Capitalize all prepositions in the title.
22. Expand your vocabulary and use new words. Do not limit yourself only to the keywords I provided.
23. You are allowed to slightly alter the tags, such as "Humiliation" to "Humiliating".
24. Important: Get wild (sexually). Research porn and JAV sites.
25. Pretend every title you give is intended for a big porn site like Pornhub or similar and 
write it accordingly while keeping JAV structure and topics in mind.
26. Double-check compliance with all rules before outputting. If a violation occurs, rewrite until it is fixed.

Examples
Example 1 input: [INCT-001] Doll Play Ichigo Aoi dressed with 
Cosplay / Actress: Ichigo Aoi / Tags: Cosplay, Creampie, Mini, Shaved
Example 1 bad outputs: [INCT-001] Ichigo Aoi Dressed In Cosplay; 
[AMBI-047] Aoi Ichigo in 3P & Shaved Passion; 
[AMBI-047] Aoi Ichigo in Shaved Stepbrother 3P
Example 1 outputs: [INCT-001] Cosplayer Ichigo Aoi Fucking Her Stepbrothers; 
[INCT-001] Shaved Ichigo Aoi Fucking Her Stepbrothers; 
[INCT-001] Ichigo Aoi Cosplay & Threesome With Her Stepbrothers; 
[INCT-001] Ichigo Aoi Fucks Her Stepbrothers

Example 2 input: [IBW-478z] Katsushika Joint Quay Complex Sunburn Girl Obscene Video / Tsuchiya Asami, 
Usui Aimi, Kawagoe Yui, Kagami Shuna, Miyazaki Kaho / Mini, R*pe, Other fetish
Example 2 bad outputs: [IBW-478z] Mini Asami Tsuchiya's Tanned Quay Lewd Escapade, 
[IBW-478z] Tanned Mini Yui Kawagoe's Naughty Quay Adventure, 
[IBW-478z] Mini Shuna Kagami's Tanned Quay Naughty Romp, 
[IBW-478z] Tanned Mini Aimi Usui's Lewd Quay Escapade, [IBW-478z] Mini Kaho Miyazaki's Tanned Quay Raunchy Fling, 
[IBW-478z] Mini Shuna Kagami & Yui Kawagoe's Tanned Quay Lewd Fucks
Example 2 good output: [IBW-478z] Tanned Mini Shuna Kagami's Quay Slutty Bang Fest, 
[IBW-478z] Tanned Mini Kaho Miyazaki's Slutty Quay Pounding, 
[IBW-478z] Shuna Kagami & Yui Kawagoe's Mini Quay Cum Bash
    """

    @property
    def database_dsn(self) -> MongoDsn:
        dsn = MongoDsn.build(
            scheme="mongodb",
            host=self.DB_HOST,
            port=27017,
            username=self.DB_USER,
            password=self.DB_PASS,
        )
        return dsn


config = Config()
