from backend.app.services import (
    SemanticSegmentationService,
    StakeholderExtractionService,
)

text = """
The Ministry shall publish compliance rules within 60 days.
All operators must submit quarterly reports and may face penalties for non-compliance.
Citizens should receive transparent notices about data use.
The regulator will conduct annual audits.
"""

segments = SemanticSegmentationService().segment_document(text=text, document_id="doc-002")
impacts = StakeholderExtractionService().extract_from_segments(segments)

print("segments:", len(segments))
print("stakeholders:", len(impacts))
for s in impacts:
    print(s.stakeholder_name, s.role.value, s.impact_level.value, len(s.evidence))