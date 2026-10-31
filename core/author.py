"""Author metadata, permutations, and Schema.org JSON-LD generation for SEO entity resolution."""

import itertools
import json

AUTHOR_INFO = {
    "name": "Potluri Krishna Priyatham",
    "primary_alias": "Kittu Priyatham",
    "role": "PhD Scholar",
    "organization": "SRM AP University",
    "research_field": "Quantum Technologies & Quantum Computing",
    "domains": [
        "Quantum Technologies",
        "Artificial Intelligence & Machine Learning",
        "Software Engineering & Distributed Systems",
        "Robotics, IoT & Embedded Systems",
        "Deep Learning & Data Science",
    ],
    "bio_short": (
        "PhD Scholar in Quantum Technologies at SRM AP University. "
        "Experienced in Software Engineering, AI/ML, Quantum Computing architectures, and IoT."
    ),
    "bio_full": (
        "I am a PhD Scholar at SRM University-AP researching Quantum Technologies and Quantum Computing. "
        "With a strong background spanning software engineering, distributed systems, deep learning/AI, "
        "and embedded IoT/robotics, I build practical tools, research algorithms, and write about "
        "modern tech architectures and quantum systems."
    ),
    "urls": {
        "portfolio": "https://potluri-krishna-priyatham.tech",
        "blog": "https://blog.potluri-krishna-priyatham.tech",
        "youtube": "https://www.youtube.com/@potlurikrishnapriyatham",
        "facebook_page": "https://www.facebook.com/people/KrishnaPriyatham/61552106248522/",
        "facebook_profile": "https://www.facebook.com/kittupriyatham",
        "github": "https://github.com/kittupriyatham",
        "linkedin": "https://www.linkedin.com/in/potluri-krishna-priyatham/",
        "x": "https://x.com/kittupriyatham",
        "twitter": "https://twitter.com/kittupriyatham",
        "instagram": "https://www.instagram.com/kittupriyatham/",
        "bluesky": "https://bsky.app/profile/kittupriyatham.bsky.social",
        "pinterest": "https://in.pinterest.com/kittupriyatham/",
        "pinterest_old": "https://www.pinterest.com/potluri_krishna_priyatham/",
    },
    "scholarly": {
        "orcid": "0000-0001-8770-0058",
        "orcid_url": "https://orcid.org/0000-0001-8770-0058",
        "google_scholar": "https://scholar.google.com/citations?user=LVCDDBYAAAAJ&hl=en",
        "researchgate": "https://www.researchgate.net/profile/Potluri-Krishna-Priyatham",
        "ieee_id": "97665626",
        "ieee_url": "https://ieeexplore.ieee.org/author/97665626",
        "researcherid": "RJU-6786-2026",
        "wos_url": "https://www.webofscience.com/wos/author/record/RJU-6786-2026",
        "openreview": "https://openreview.net/profile?id=%7EPOTLURI_KRISHNA_PRIYATHAM1",
        "arxiv_username": "kittupriyatham",
        "arxiv_url": "https://arxiv.org/search/?searchtype=author&query=Priyatham%2C+P+K",
    },
}


def _generate_alternate_names() -> list[str]:
    names: set[str] = set()

    # Core full variations
    names.add("Potluri Krishna Priyatham")
    names.add("Krishna Priyatham Potluri")
    names.add("Kittu Priyatham")
    names.add("Priyatham Potluri")
    names.add("Potluri Priyatham")
    names.add("Krishna Potluri")
    names.add("Potluri Krishna")
    names.add("Krishna Priyatham")
    names.add("Priyatham Krishna")
    names.add("Priyatham Krishna Potluri")

    # Handles & slugs
    handles = [
        "kittupriyatham", "potlurikrishnapriyatham", "krishnapriyatham",
        "priyathampotluri", "potluripriyatham", "krishnapotluri",
        "kittu", "priyatham", "krishna", "potluri"
    ]
    for h in handles:
        names.add(h)
        names.add(h.lower())
        names.add(h.capitalize())
        names.add(h.upper())

    def add_token_permutations(tokens: list[str]):
        for r in range(2, len(tokens) + 1):
            for perm in itertools.permutations(tokens, r):
                names.add(" ".join(perm))
                names.add(" ".join(perm).lower())
                names.add(" ".join(perm).upper())

                for mask in range(1, 1 << len(perm)):
                    words = []
                    for i in range(len(perm)):
                        if mask & (1 << i):
                            words.append(perm[i][0])
                        else:
                            words.append(perm[i])

                    names.add(" ".join(words))
                    names.add(" ".join(words).lower())
                    names.add(" ".join(words).upper())

                    dotted_space = " ".join(w + "." if len(w) == 1 else w for w in words)
                    names.add(dotted_space)
                    names.add(dotted_space.lower())
                    names.add(dotted_space.upper())

                    dotted_compact = "".join(w + "." if len(w) == 1 else w for w in words)
                    names.add(dotted_compact)
                    names.add(dotted_compact.lower())
                    names.add(dotted_compact.upper())

                    joined = "".join(words)
                    names.add(joined)
                    names.add(joined.lower())
                    names.add(joined.upper())

                    dots_between = ".".join(words)
                    names.add(dots_between)
                    names.add(dots_between.lower())
                    names.add(dots_between.upper())

    add_token_permutations(["Potluri", "Krishna", "Priyatham"])
    add_token_permutations(["Kittu", "Priyatham"])
    add_token_permutations(["Potluri", "Kittu", "Priyatham"])

    return sorted(list(names))


ALTERNATE_NAMES = _generate_alternate_names()


def get_author_schema() -> dict:
    scholarly = AUTHOR_INFO.get("scholarly", {})
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": AUTHOR_INFO["name"],
        "alternateName": ALTERNATE_NAMES,
        "url": AUTHOR_INFO["urls"]["portfolio"],
        "sameAs": [
            AUTHOR_INFO["urls"]["blog"],
            AUTHOR_INFO["urls"]["portfolio"],
            scholarly.get("orcid_url", "https://orcid.org/0000-0001-8770-0058"),
            scholarly.get("google_scholar", ""),
            scholarly.get("researchgate", ""),
            scholarly.get("openreview", ""),
            scholarly.get("ieee_url", ""),
            scholarly.get("wos_url", ""),
            AUTHOR_INFO["urls"]["youtube"],
            AUTHOR_INFO["urls"]["facebook_page"],
            AUTHOR_INFO["urls"]["facebook_profile"],
            AUTHOR_INFO["urls"]["github"],
            AUTHOR_INFO["urls"]["linkedin"],
            AUTHOR_INFO["urls"]["twitter"],
            AUTHOR_INFO["urls"]["instagram"],
            AUTHOR_INFO["urls"]["bluesky"],
            AUTHOR_INFO["urls"]["pinterest"],
        ],
        "identifier": [
            {
                "@type": "PropertyValue",
                "propertyID": "ORCID",
                "value": scholarly.get("orcid", "0000-0001-8770-0058"),
            },
            {
                "@type": "PropertyValue",
                "propertyID": "Web of Science ResearcherID",
                "value": scholarly.get("researcherid", "RJU-6786-2026"),
            },
            {
                "@type": "PropertyValue",
                "propertyID": "IEEE Author ID",
                "value": scholarly.get("ieee_id", "97665626"),
            },
        ],
        "jobTitle": f"{AUTHOR_INFO['role']} in {AUTHOR_INFO['research_field']}",
        "worksFor": {
            "@type": "CollegeOrUniversity",
            "name": AUTHOR_INFO["organization"],
            "url": "https://srmap.edu.in",
        },
        "knowsAbout": AUTHOR_INFO["domains"],
    }


def get_author_schema_json() -> str:
    return json.dumps(get_author_schema(), ensure_ascii=False)
