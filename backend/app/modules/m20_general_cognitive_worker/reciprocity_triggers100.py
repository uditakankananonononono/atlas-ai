"""Transparent optional-offer declaration check; PREP only, no obligation creation."""
from fractions import Fraction
class Reciprocity100Error(ValueError):pass

def _refuse(code):raise Reciprocity100Error('RECIPR100: '+code)
def prepare_reciprocity(packet):
 if type(packet)is not dict or set(packet)!={'benefit','strings_attached','expected_return','disclosed_to_recipient','decline_without_penalty'}:_refuse('packet schema')
 for key in ('benefit','expected_return'):
  value=packet[key]
  if key=='expected_return' and value is None:continue
  if type(value)is not str or len(value)>2000 or not value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):_refuse('invalid '+key)
 for key in ('strings_attached','disclosed_to_recipient','decline_without_penalty'):
  if type(packet[key])is not bool:_refuse('invalid '+key)
 risk=(Fraction(3,5) if packet['strings_attached'] else Fraction(0))+(Fraction(2,5) if packet['expected_return'] is not None else Fraction(0))
 optional=risk==0 and packet['disclosed_to_recipient'] and packet['decline_without_penalty']
 return {**packet,'declared_risk':str(risk),'transparent_optional_offer':optional,'send_authorized':False,'real_world_intent_verified':False,
  'no_obligation_language':'This is offered without obligation. You may decline without penalty.',
  'scope':'declared_offer_checklist_only','ethical_boundary':'No covert indebtedness, coercion, targeting or efficacy claim. Declarations are not verified recipient consent.'}
