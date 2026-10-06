
from __future__ import annotations
import math, re
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd

MONTHS = {
    "january":1,"jan":1,"february":2,"feb":2,"march":3,"mar":3,"april":4,"apr":4,
    "may":5,"june":6,"jun":6,"july":7,"jul":7,"august":8,"aug":8,"september":9,
    "sep":9,"sept":9,"october":10,"oct":10,"november":11,"nov":11,"december":12,"dec":12
}
MONTH_LABELS = {i: pd.Timestamp(2000,i,1).strftime("%B") for i in range(1,13)}

ALIASES = {
    "trauma":"Trauma/Injury","injury":"Trauma/Injury","cardiac":"Cardiac",
    "respiratory":"Respiratory","breathing":"Respiratory","neuro":"Neurologic",
    "neurological":"Neurologic","diabetic":"Endocrine/Metabolic","diabetes":"Endocrine/Metabolic",
    "syncope":"LOC/Syncope","fainting":"LOC/Syncope","psychiatric":"Behavioral/Psychiatric",
    "behavioral":"Behavioral/Psychiatric"
}

def norm(x: Any) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip().lower()

def load_clean(path: str|Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    numeric = ["age","year","month","hour","zone_number","turnout_min_valid","dispatch_to_scene_min_valid",
               "scene_to_patient_min_valid","scene_time_min_valid","transport_min_valid",
               "destination_to_available_min_valid","commitment_min_valid"]
    for c in numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def load_concurrency(path: str|Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    for c in ["active_incidents_at_start","other_active_at_start","overlapping_other_incidents","duration_min","year","month","hour"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["concurrent_2plus_at_start","concurrent_3plus_at_start","concurrent_4plus_at_start"]:
        if c in df.columns and df[c].dtype != bool:
            df[c] = df[c].astype(str).str.lower().eq("true")
    return df

def uniques(df: pd.DataFrame, col: str) -> List[str]:
    if col not in df.columns: return []
    vals = df[col].dropna().astype(str)
    return sorted([v for v in vals.unique() if v and v.lower()!="nan"], key=str.lower)

def f(field, op, value, label=None):
    return {"field":field,"op":op,"value":value,"label":label or f"{field} {op} {value}"}

def apply_filters(df: pd.DataFrame, filters: List[Dict[str,Any]]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for x in filters:
        if x["field"] not in df.columns:
            mask &= False; continue
        s=df[x["field"]]; op=x["op"]; v=x["value"]
        if op=="==": mask &= s.eq(v)
        elif op=="!=": mask &= s.ne(v)
        elif op=="<": mask &= pd.to_numeric(s,errors="coerce").lt(v)
        elif op=="<=": mask &= pd.to_numeric(s,errors="coerce").le(v)
        elif op==">": mask &= pd.to_numeric(s,errors="coerce").gt(v)
        elif op==">=": mask &= pd.to_numeric(s,errors="coerce").ge(v)
        elif op=="in": mask &= s.isin(v)
    return mask.fillna(False)

def calc(df: pd.DataFrame, event_filters, condition_filters):
    cm = apply_filters(df, condition_filters) if condition_filters else pd.Series(True,index=df.index)
    em = apply_filters(df, event_filters) if event_filters else pd.Series(True,index=df.index)
    den=int(cm.sum()); num=int((cm&em).sum()); p=(num/den if den else None)
    return {"numerator":num,"denominator":den,"probability":p,"mask":cm&em,"condition_mask":cm}

def wilson(num:int, den:int, z:float=1.959963984540054):
    if den<=0: return (None,None)
    p=num/den
    d=1+z*z/den
    center=(p+z*z/(2*den))/d
    half=z*math.sqrt((p*(1-p)+z*z/(4*den))/den)/d
    return max(0,center-half), min(1,center+half)

def odds_ratio(a,b,c,d):
    # Haldane-Anscombe correction only if needed.
    vals=[a,b,c,d]
    if any(v==0 for v in vals): vals=[v+0.5 for v in vals]
    a,b,c,d=vals
    return (a*d)/(b*c) if b*c else None

def filter_label(x):
    return x.get("label") or f"{x['field']} {x['op']} {x['value']}"

def notation(event_filters, condition_filters):
    def compact(fs):
        out=[]
        for x in fs:
            if x["field"] in ("impression_family","dispatch_family"):
                out.append(str(x["value"]))
            elif x["field"]=="age": out.append(f"Age{x['op']}{x['value']}")
            elif x["field"]=="month":
                v=x["value"]
                if isinstance(v,(list,tuple,set)):
                    labels=[MONTH_LABELS.get(int(m),str(m)) for m in v]
                    out.append("Month ∈ {" + ", ".join(labels) + "}")
                else:
                    out.append(MONTH_LABELS.get(int(v),str(v)))
            elif x["field"].startswith("concurrent_"):
                n={"concurrent_2plus_at_start":"≥2 concurrent",
                   "concurrent_3plus_at_start":"≥3 concurrent",
                   "concurrent_4plus_at_start":"≥4 concurrent"}.get(x["field"],x["field"])
                out.append(n)
            elif x.get("op")=="in" and isinstance(x.get("value"),(list,tuple,set)):
                vals=[str(v) for v in x["value"]]
                out.append(f"{x['field']} ∈ {{" + ", ".join(vals) + "}}")
            else:
                out.append(filter_label(x))
        return " ∩ ".join(out) if out else "All incidents"
    a=compact(event_filters); b=compact(condition_filters)
    return f"P({a} | {b})" if condition_filters else f"P({a})"

def parse_age(s, out):
    m=re.search(r"(?:age\s*)?(?:<|under|younger than|less than)\s*(\d+(?:\.\d+)?)",s)
    if m: out.append(f("age","<",float(m.group(1)),f"Age < {m.group(1)}")); return
    m=re.search(r"(?:age\s*)?(?:>|over|older than|greater than)\s*(\d+(?:\.\d+)?)",s)
    if m: out.append(f("age",">",float(m.group(1)),f"Age > {m.group(1)}")); return
    m=re.search(r"(?:age\s*)?(\d+)\s*(?:-|to|through)\s*(\d+)",s)
    if m:
        out += [f("age",">=",int(m.group(1)),f"Age ≥ {m.group(1)}"),
                f("age","<=",int(m.group(2)),f"Age ≤ {m.group(2)}")]

def parse_nl(text:str, clean:pd.DataFrame):
    t=norm(text)
    left,right=t,""
    m=re.search(r"p\s*\((.*?)\|(.*?)\)",t)
    if m: left,right=m.group(1),m.group(2)
    else:
        m=re.search(r"(.+?)\s+(?:given|among|where|when)\s+(.+)",t)
        if m: left,right=m.group(1),m.group(2)
        else:
            m=re.search(r"(?:probability|chance|likelihood)\s+of\s+(.+?)\s+(?:for|in)\s+(.+)",t)
            if m: left,right=m.group(1),m.group(2)

    impression=uniques(clean,"impression_family")
    dispatch=uniques(clean,"dispatch_family")

    def best(s, vals):
        for a,v in ALIASES.items():
            if re.search(rf"\b{re.escape(a)}\b",s) and v in vals: return v
        for v in sorted(vals,key=len,reverse=True):
            if norm(v) in s:return v
        return None

    def segment(s):
        out=[]; s=norm(s)
        fam=best(s,impression)
        if fam: out.append(f("impression_family","==",fam,f"Provider impression = {fam}"))
        if "dispatch" in s or "complaint" in s:
            dfam=best(s,dispatch)
            if dfam:
                out=[x for x in out if x["field"]!="impression_family"]
                out.append(f("dispatch_family","==",dfam,f"Dispatch family = {dfam}"))
        parse_age(s,out)
        for name,num in MONTHS.items():
            if re.search(rf"\b{re.escape(name)}\b",s):
                out.append(f("month","==",num,f"Month = {MONTH_LABELS[num]}")); break
        if "weekend" in s: out.append(f("is_weekend","==",True,"Weekend"))
        for fld,n in [("concurrent_4plus_at_start",4),("concurrent_3plus_at_start",3),("concurrent_2plus_at_start",2)]:
            if re.search(rf"(?:>=|≥|at least|{n}\+)\s*{n if False else ''}\s*(?:concurrent|simultaneous)",s) or f"{n}+ concurrent" in s:
                out.append(f(fld,"==",True,f"At least {n} incidents active at dispatch")); break
        if "turnout" in s and ("under 2" in s or "within 2" in s or "≤ 2" in s):
            out.append(f("turnout_le_2m","==",True,"Turnout ≤ 2 min"))
        zm=re.search(r"\bzone\s+([0-9]{1,2}(?:-[a-z]+)?)\b",s)
        if zm:
            z=zm.group(1).upper()
            out.append(f("zone_norm","==",z,f"Zone = {z}"))
        return out

    if right:
        return segment(left),segment(right),"clean"
    allf=segment(t)
    clinical=[x for x in allf if x["field"] in ("impression_family","dispatch_family")]
    contextual=[x for x in allf if x not in clinical]
    return (clinical[:1] if clinical else allf[:1]), (contextual if clinical else allf[1:]), "clean"


def apply_filter_group(df: pd.DataFrame, filters: List[Dict[str,Any]], logic: str="AND") -> pd.Series:
    if not filters:
        return pd.Series(True, index=df.index)
    masks = [apply_filters(df, [x]) for x in filters]
    if logic.upper() == "OR":
        out = pd.Series(False, index=df.index)
        for m in masks:
            out |= m
        return out.fillna(False)
    out = pd.Series(True, index=df.index)
    for m in masks:
        out &= m
    return out.fillna(False)


def calc_boolean(df: pd.DataFrame, event_groups, condition_groups):
    def groups_mask(groups):
        mask = pd.Series(True, index=df.index)
        for g in groups:
            gm = apply_filter_group(df, g.get("filters", []), g.get("logic", "AND"))
            if g.get("negate", False):
                gm = ~gm
            mask &= gm
        return mask.fillna(False)
    em = groups_mask(event_groups) if event_groups else pd.Series(True,index=df.index)
    cm = groups_mask(condition_groups) if condition_groups else pd.Series(True,index=df.index)
    den = int(cm.sum())
    num = int((em & cm).sum())
    return {"numerator":num,"denominator":den,"probability":(num/den if den else None),"mask":em&cm,"condition_mask":cm}


def two_proportion_stats(num_a, den_a, num_b, den_b, z=1.959963984540054):
    if not den_a or not den_b:
        return {}
    pa=num_a/den_a; pb=num_b/den_b; diff=pa-pb
    se=math.sqrt(pa*(1-pa)/den_a + pb*(1-pb)/den_b)
    return {
        "pa":pa,"pb":pb,"difference":diff,
        "difference_ci_low":diff-z*se,"difference_ci_high":diff+z*se,
        "risk_ratio":(pa/pb if pb>0 else None),
        "odds_ratio":odds_ratio(num_a,den_a-num_a,num_b,den_b-num_b),
    }
