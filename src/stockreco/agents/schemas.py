PROPOSER_SCHEMA = {
  "type":"object",
  "properties":{
    "as_of":{"type":"string"},
    "top10":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{
          "ticker":{"type":"string"},
          "rank":{"type":"integer"},
          "p_up":{"type":"number"},
          "signals":{"type":"object"},
          "thesis":{"type":"string"},
          "invalidate_if":{"type":"array","items":{"type":"string"}}
        },
        "required":["ticker","rank","p_up","signals","thesis","invalidate_if"],
        "additionalProperties": True
      },
      "minItems": 5,
      "maxItems": 10
    }
  },
  "required":["as_of","top10"],
  "additionalProperties": False
}

REVIEWER_SCHEMA = {
  "type":"object",
  "properties":{
    "approved":{"type":"array","items":{"type":"string"}},
    "rejected":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{"ticker":{"type":"string"},"reason":{"type":"string"}},
        "required":["ticker","reason"],
        "additionalProperties": False
      }
    }
  },
  "required":["approved","rejected"],
  "additionalProperties": False
}

ANALYST_SCHEMA = {
  "type":"object",
  "properties":{
    "final":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{
          "ticker":{"type":"string"},
          "p_up":{"type":"number"},
          "confidence_label":{"type":"string"},
          "why":{"type":"string"},
          "options_playbook":{"type":"array","items":{"type":"string"}}
        },
        "required":["ticker","p_up","confidence_label","why","options_playbook"],
        "additionalProperties": False
      },
      "minItems": 1,
      "maxItems": 10
    },
    "regime_notes":{"type":"array","items":{"type":"string"}}
  },
  "required":["final","regime_notes"],
  "additionalProperties": False
}
