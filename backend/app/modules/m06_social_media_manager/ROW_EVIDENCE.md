# Rows 400-426 evidence map (base snapshot 132234c)

Suite: `pytest tests/ -q` -> 119 passed (81 pre-existing + 38 new), offline.

| Row | Feature | Endpoint | Test(s) |
|---|---|---|---|
| 400 | Sample Size Calculation | `POST /social-media-manager/marketing/sample-size` | `test_m06_marketing.py::test_row_400_sample_size_exact_math, ::test_row_400_sample_size_rejects_impossible_mde` |
| 401 | Segmentation Analysis | `POST /social-media-manager/marketing/segmentation` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[segmentation]` |
| 402 | Targeting Strategy | `POST /social-media-manager/marketing/targeting` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[targeting]` |
| 403 | Positioning Strategy | `POST /social-media-manager/marketing/positioning` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[positioning]` |
| 404 | Brand Architecture | `POST /social-media-manager/marketing/brand-architecture` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[brand-architecture]` |
| 405 | Brand Voice Development | `POST /social-media-manager/marketing/brand-voice` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[brand-voice]` |
| 406 | Messaging Framework | `POST /social-media-manager/marketing/messaging-framework` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[messaging-framework]` |
| 407 | Copywriting | `POST /social-media-manager/marketing/copywriting` | `test_m06_marketing.py::test_row_407_copywriting_success_with_findings, ::test_row_407_copywriting_sponsored_without_disclosure_is_422_and_unstored` |
| 408 | Content Strategy | `POST /social-media-manager/marketing/content-strategy` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[content-strategy]` |
| 409 | Editorial Calendar | `POST /social-media-manager/marketing/editorial-calendar` | `test_m06_marketing.py::test_row_409_editorial_calendar_drafts_only, ::test_row_409_editorial_calendar_rejects_bad_start_date` |
| 410 | SEO Optimization | `POST /social-media-manager/marketing/seo-optimization` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[seo-optimization]` |
| 411 | Keyword Research | `POST /social-media-manager/marketing/keyword-research` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[keyword-research]` |
| 412 | Link Building | `POST /social-media-manager/marketing/link-building` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[link-building]` |
| 413 | Technical SEO | `POST /social-media-manager/marketing/technical-seo` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[technical-seo]` |
| 414 | Local SEO | `POST /social-media-manager/marketing/local-seo` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[local-seo]` |
| 415 | Content Marketing | `POST /social-media-manager/marketing/content-marketing` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[content-marketing]` |
| 416 | Thought Leadership | `POST /social-media-manager/marketing/thought-leadership` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[thought-leadership]` |
| 417 | Public Relations | `POST /social-media-manager/marketing/public-relations` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[public-relations]` |
| 418 | Media Relations | `POST /social-media-manager/marketing/media-relations` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[media-relations]` |
| 419 | Crisis Communication | `POST /social-media-manager/marketing/crisis-communication` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[crisis-communication]` |
| 420 | Social Media Strategy | `POST /social-media-manager/marketing/social-media-strategy` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[social-media-strategy]` |
| 421 | Community Management | `POST /social-media-manager/marketing/community-management` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[community-management]` |
| 422 | Influencer Marketing | `POST /social-media-manager/marketing/influencer-marketing` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[influencer-marketing]` |
| 423 | Affiliate Marketing | `POST /social-media-manager/marketing/affiliate-marketing` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[affiliate-marketing]` |
| 424 | Referral Programs | `POST /social-media-manager/marketing/referral-program` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[referral-program]` |
| 425 | Email Marketing | `POST /social-media-manager/marketing/email-marketing` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[email-marketing]` |
| 426 | Marketing Automation | `POST /social-media-manager/marketing/marketing-automation` | `test_m06_marketing.py::test_row_generic_artifact_endpoint[marketing-automation]` |

Safety/honesty tests (cross-row): test_keyword_research_strips_unprovided_volumes,
test_keyword_research_keeps_caller_provided_volumes, test_link_building_without_prospects_names_nobody,
test_link_building_targets_limited_to_provided_prospects, test_malformed_llm_reply_is_502,
test_provider_failure_is_503, test_artifact_listing_filters_by_kind,
test_sql_repository_artifact_round_trip_is_tenant_scoped.

Gaps:
- LLM-backed rows produce draft artifacts; quality depends on the caller's BYOK model.
- No execution: automation/email artifacts are definitions/drafts only; M06 has no email sender or workflow engine (by design).
- SEO rows analyze caller-provided facts only; nothing is crawled.

# Rows 281-305 evidence map (base snapshot 484f09c)

Suite: `pytest tests/ -q` -> 150 passed (119 pre-existing + 31 new), offline.

| Row | Feature | Endpoint | Test |
|---|---|---|---|
| 281 | Color Theory Application | `POST /social-media-manager/creative/color-theory` | `test_m06_creative.py::test_row_creative_spec_endpoint[color-theory]` |
| 282 | Composition Principles | `POST /social-media-manager/creative/composition` | `test_m06_creative.py::test_row_creative_spec_endpoint[composition]` |
| 283 | Typography Selection | `POST /social-media-manager/creative/typography` | `test_m06_creative.py::test_row_creative_spec_endpoint[typography]` |
| 284 | Logo Design | `POST /social-media-manager/creative/logo-design` | `test_m06_creative.py::test_row_creative_spec_endpoint[logo-design]` |
| 285 | Brand Identity Systems | `POST /social-media-manager/creative/brand-identity` | `test_m06_creative.py::test_row_creative_spec_endpoint[brand-identity]` |
| 286 | Packaging Design | `POST /social-media-manager/creative/packaging-design` | `test_m06_creative.py::test_row_creative_spec_endpoint[packaging-design]` |
| 287 | UI/UX Design | `POST /social-media-manager/creative/ui-ux-design` | `test_m06_creative.py::test_row_creative_spec_endpoint[ui-ux-design]` |
| 288 | Information Architecture | `POST /social-media-manager/creative/information-architecture` | `test_m06_creative.py::test_row_creative_spec_endpoint[information-architecture]` |
| 289 | Interaction Design | `POST /social-media-manager/creative/interaction-design` | `test_m06_creative.py::test_row_creative_spec_endpoint[interaction-design]` |
| 290 | Motion Design | `POST /social-media-manager/creative/motion-design` | `test_m06_creative.py::test_row_creative_spec_endpoint[motion-design]` |
| 291 | 3D Modeling | `POST /social-media-manager/creative/3d-modeling` | `test_m06_creative.py::test_row_creative_spec_endpoint[3d-modeling]` |
| 292 | Texture Creation | `POST /social-media-manager/creative/texture-creation` | `test_m06_creative.py::test_row_creative_spec_endpoint[texture-creation]` |
| 293 | Lighting Design | `POST /social-media-manager/creative/lighting-design` | `test_m06_creative.py::test_row_creative_spec_endpoint[lighting-design]` |
| 294 | Rendering Optimization | `POST /social-media-manager/creative/rendering-optimization` | `test_m06_creative.py::test_row_creative_spec_endpoint[rendering-optimization]` |
| 295 | Animation Principles | `POST /social-media-manager/creative/animation-principles` | `test_m06_creative.py::test_row_creative_spec_endpoint[animation-principles]` |
| 296 | Character Rigging | `POST /social-media-manager/creative/character-rigging` | `test_m06_creative.py::test_row_creative_spec_endpoint[character-rigging]` |
| 297 | Facial Animation | `POST /social-media-manager/creative/facial-animation` | `test_m06_creative.py::test_row_creative_spec_endpoint[facial-animation]` |
| 298 | Physics Simulation | `POST /social-media-manager/creative/physics-simulation` | `test_m06_creative.py::test_row_creative_spec_endpoint[physics-simulation]` |
| 299 | Particle Effects | `POST /social-media-manager/creative/particle-effects` | `test_m06_creative.py::test_row_creative_spec_endpoint[particle-effects]` |
| 300 | Procedural Generation | `POST /social-media-manager/creative/procedural-generation` | `test_m06_creative.py::test_row_creative_spec_endpoint[procedural-generation]` |
| 301 | Sound Design | `POST /social-media-manager/creative/sound-design` | `test_m06_creative.py::test_row_creative_spec_endpoint[sound-design]` |
| 302 | Music Composition | `POST /social-media-manager/creative/music-composition` | `test_m06_creative.py::test_row_creative_spec_endpoint[music-composition]` |
| 303 | Harmony Arrangement | `POST /social-media-manager/creative/harmony-arrangement` | `test_m06_creative.py::test_row_creative_spec_endpoint[harmony-arrangement]` |
| 304 | Rhythm Programming | `POST /social-media-manager/creative/rhythm-programming` | `test_m06_creative.py::test_row_creative_spec_endpoint[rhythm-programming]` |
| 305 | Orchestration | `POST /social-media-manager/creative/orchestration` | `test_m06_creative.py::test_row_creative_spec_endpoint[orchestration]` |

Boundary tests: test_asset_prompts_limited_to_self_hosted_engines,
test_style_imitation_is_redacted_and_recorded, test_clean_output_has_no_originality_notes,
test_malformed_llm_reply_is_502, test_provider_failure_is_503,
test_creative_artifacts_visible_in_shared_listing.

Gaps:
- Specifications only: no render/audio pipeline is invoked or verified; quality of any
  later render depends on the human/pipeline executing the spec.
- Imitation guard is a lexical scan; it catches 'in the style of <name>' phrasing, not
  paraphrased imitation requests.
