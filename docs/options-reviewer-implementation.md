# Options UI Enhancement - Reviewer Status Display

## Summary

Enhanced the Options Recommendations page to clearly show reviewer approval status, adjust confidence display based on reviewer decisions, and sort recommendations with approved items first.

---

## Changes Made

### 1. Enhanced Data Parsing

**File:** [OptionsRecommendations.jsx](file:///Users/vinodkeshav/myprojects/stockreco/frontend/src/pages/OptionsRecommendations.jsx)

**What Changed:**
- Parse both `approved` and `rejected` recommendations from the reviewer
- Enrich each row with `__reviewerApproved` or `__reviewerRejected` flags
- Include rejection reasons in `__rejectionReason` field
- Display both approved AND rejected items for full transparency

**Key Logic:**
```javascript
// Track approved symbols
approved.forEach(r => {
    const key = `${r.symbol}-${r.strike}-${r.side}-${r.expiry}`;
    approvedSymbols.add(key);
});

// Track rejected with reasons
rejected.forEach(r => {
    const key = `${r.symbol}-${r.strike}-${r.side}-${r.expiry}`;
    rejectedMap.set(key, r.reason);
});

// Mark all rows with approval status
rows = rows.map(r => {
    const key = `${r.symbol}-${r.strike}-${r.side}-${r.expiry}`;
    if (approvedSymbols.has(key)) {
        return { ...r, __reviewerApproved: true };
    }
    return r;
});
```

### 2. Added Reviewer Status Column

**File:** [_RecoPage.jsx](file:///Users/vinodkeshav/myprojects/stockreco/frontend/src/pages/_RecoPage.jsx)

**Visual Indicators:**

**✅ APPROVED Badge** (Green)
- Emerald background with checkmark icon
- Indicates recommendation passed all reviewer filters
- High confidence, good risk/reward

**❌ REJECTED Badge** (Red)
- Rose background with X icon
- Shows on hover: detailed rejection reason
- Examples:
  - "IV 75.0% exceeds 60.0% threshold"
  - "DTE 3 below minimum 5 for strict mode"
  - "Confidence 0.25 below 0.35 threshold"

**— No Status**
- For old data without reviewer information
- Neutral gray indicator

### 3. Adjusted Confidence Display

**Approved Items:**
- **Green bold text** (emerald-700)
- Shows original confidence percentage
- Example: **45%** in green

**Rejected Items:**
- **Strikethrough text** in faded red (rose-400)
- Confidence set to 0% with strikethrough
- Example: ~~25%~~ in faded red
- Visual cue that this recommendation should not be traded

**No Status:**
- Regular slate-700 text
- Shows original confidence

### 4. Improved Sorting

**New Sort Order:**
1. **Approved recommendations** (highest priority)
2. **No status** (middle priority - old data)
3. **Rejected recommendations** (lowest priority)
4. **Within each group:** Sort by confidence (highest first)

**Code:**
```javascript
.sort((a, b) => {
    // Sort by reviewer status first (approved > no status > rejected)
    const statusA = a.__reviewerApproved ? 2 : a.__reviewerRejected ? 0 : 1;
    const statusB = b.__reviewerApproved ? 2 : b.__reviewerRejected ? 0 : 1;
    if (statusA !== statusB) return statusB - statusA;
    
    // Then by confidence descending (highest first)
    const confA = Number(a.confidence) || 0;
    const confB = Number(b.confidence) || 0;
    return confB - confA;
});
```

---

## Visual Examples

### Table Display

```
Symbol      Action  Option              LTP    Entry  SL    T1    T2    Sell-by    Reviewer    Conf
────────────────────────────────────────────────────────────────────────────────────────────────────
NIFTY       BUY     24500 CE (26-Dec)   120    116    75    165   215   2025-12-18  ✓ APPROVED  45%
BANKNIFTY   BUY     52000 PE (26-Dec)   180    175    110   240   305   2025-12-20  ✓ APPROVED  42%
RELIANCE    BUY     1300 CE (26-Dec)    25     24     15    32    40    2025-12-19  ✗ REJECTED  ~~30%~~
TCS         BUY     4200 PE (26-Dec)    35     34     21    45    56    2025-12-18  ✗ REJECTED  ~~28%~~
```

### Hover Tooltips

When hovering over **REJECTED** badge:
- "IV 75.0% exceeds 60.0% threshold (high premium/IV crush risk)"
- "DTE 3 below minimum 5 for strict mode (theta cliff risk)"
- "Confidence 0.30 below 0.35 threshold for strict mode"
- "Theta decay 10.5% of entry per day exceeds 8.0% threshold"

---

## Benefits

### 1. **Clear Quality Indicators**
Users can immediately see which recommendations passed quality filters

### 2. **Risk Transparency**
Rejected items show exactly why they were filtered out

### 3. **Better Decision Making**
- Focus on approved items (shown first)
- Understand rejection reasons for learning
- See full picture (not just approved items)

### 4. **Confidence Clarity**
- Green confidence = approved, trade-worthy
- Strikethrough confidence = rejected, avoid trading
- Visual reinforcement of reviewer decision

### 5. **Educational Value**
Rejection reasons help users understand:
- What makes a good vs bad option trade
- Risk factors to watch (IV, theta, DTE)
- Mode-specific thresholds

---

## User Workflow

### Before Enhancement
1. See all recommendations with same confidence display
2. No indication of quality or risk
3. Manual filtering required
4. No understanding of why some might be risky

### After Enhancement
1. **See approved items first** (green badges, green confidence)
2. **Quickly identify rejected items** (red badges, strikethrough)
3. **Hover for rejection details** (educational)
4. **Focus trading on approved items** (clear visual priority)
5. **Learn from rejections** (understand risk factors)

---

## Technical Details

### Data Flow

```
Backend (run_eod_option_reco.py)
    ↓
    Generates: {recommender: [...], reviewer: {approved: [...], rejected: [...]}, final: [...]}
    ↓
Frontend API (/api/options/2025-12-15)
    ↓
OptionsRecommendations.jsx (pickOptionsRows)
    ↓
    Enriches rows with __reviewerApproved, __reviewerRejected, __rejectionReason
    ↓
_RecoPage.jsx (Table component)
    ↓
    Displays badges, adjusts confidence, sorts by status
```

### Backward Compatibility

- Old format (simple array): Works as before, no reviewer column
- New format without reviewer: Shows "—" in reviewer column
- New format with reviewer: Full functionality

---

## Files Modified

1. [OptionsRecommendations.jsx](file:///Users/vinodkeshav/myprojects/stockreco/frontend/src/pages/OptionsRecommendations.jsx)
   - Enhanced `pickOptionsRows()` to parse reviewer data
   - Enrich rows with approval/rejection status
   - Updated subtitle

2. [_RecoPage.jsx](file:///Users/vinodkeshav/myprojects/stockreco/frontend/src/pages/_RecoPage.jsx)
   - Added "Reviewer" column to table header
   - Display approval/rejection badges with icons
   - Adjust confidence display (green/strikethrough)
   - Improved sorting (approved first)

---

## Next Steps (Optional)

1. **Rejection Details Modal**: Click rejected badge to see full details
2. **Filter Controls**: Toggle to show/hide rejected items
3. **Statistics Summary**: Show count of approved vs rejected
4. **Export Approved Only**: Download CSV with only approved recommendations
5. **Rejection Analytics**: Track most common rejection reasons over time
