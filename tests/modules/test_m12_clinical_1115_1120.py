import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://standard.test/v1','source_title':'Standard'}
def image(method):return clinical_support(method,{'study_metadata':{'modality':'MRI'},'findings':[{'label':'lesion','confidence':.8,'location':'left','measurement':{'mm':3}}],'source':SRC})
def test_row_1115_image_analysis_organizes_provenanced_findings_not_diagnoses():
 o=image('medical_image_analysis');assert o['findings_for_specialist_review'][0]['provenance']=='external_model_or_clinician' and 'did not inspect pixels' in o['coverage_warning']
def test_row_1116_radiology_report_is_review_queue_with_study_metadata():
 o=image('radiology_report_generation');assert o['study_metadata']['modality']=='MRI' and o['mode']=='radiology_report_generation' and 'specialist' in str(o).lower()
def test_row_1117_pathology_analysis_preserves_measurements_and_boundary():
 o=image('pathology_slide_analysis');assert o['findings_for_specialist_review'][0]['measurement']=={'mm':3} and 'unlisted abnormalities' in o['coverage_warning']
def wave(method):return clinical_support(method,{'sampling_rate_hz':4,'samples':[0,1,0,-1,0,1,0,-1],'annotations':[{'at':1,'label':'external mark'}],'source':SRC})
def test_row_1118_ecg_support_reports_signal_qc_not_rhythm_diagnosis():
 o=wave('ecg_interpretation');assert o['signal_summary']['duration_seconds']==2 and o['signal_summary']['rms']==pytest.approx(2**-.5) and 'not rhythm' in o['interpretation_boundary']
def test_row_1119_eeg_support_requires_original_trace_specialist_review():
 o=wave('eeg_analysis');assert o['supplied_annotations'][0]['label']=='external mark' and 'specialist review' in o['interpretation_boundary'].lower()
def test_row_1120_genomics_matches_curated_records_and_preserves_unknowns():
 k=[{'gene':'G','variant':'v1','classification':'pathogenic','evidence_level':'expert','condition':'C',**SRC}];o=clinical_support('genomics_interpretation',{'variants':[{'gene':'G','variant':'v1'},{'gene':'G','variant':'v2'}],'knowledge_records':k});assert o['variant_interpretations'][0]['classification']=='pathogenic' and o['variant_interpretations'][1]['classification']=='not_in_supplied_knowledge' and 'not benign' in o['coverage_warning']
def test_clinical_modalities_reject_missing_source_or_bad_signal():
 with pytest.raises(ValueError):clinical_support('medical_image_analysis',{'study_metadata':{'modality':'CT'},'findings':[],'source':SRC})
 with pytest.raises(ValueError):clinical_support('ecg_interpretation',{'sampling_rate_hz':0,'samples':[1,2,3],'source':SRC})
