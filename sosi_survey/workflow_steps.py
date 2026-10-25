# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure navigation rules for the five SOSI Survey stages."""
SOURCE_CHOICES = {
    'sosi': {'title':'Åpne eksisterende SOSI-fil', 'description':'Importer og bevar hele originalfilen. Ingen geometri endres automatisk.', 'action':'Åpne SOSI-fil …'},
    'csv': {'title':'Importer feltmålinger fra CSV/TXT', 'description':'Mottakeruavhengig CSV med ID, kode, beskrivelse og kontrollert XYZ.', 'action':'Importer feltmålinger …'},
    'existing': {'title':'Bruk eksisterende QGIS-lag', 'description':'Bruk lag som allerede finnes i QGIS. Kilden beholdes uendret.', 'action':'Bruk aktivt QGIS-lag'},
    'new': {'title':'Tegn nytt SOSI-arbeidslag', 'description':'Velg SOSI-profil og opprett punkt, linje eller flate i QGIS.', 'action':'Opprett nytt arbeidslag …'},
}
def enabled_steps(*,has_layer=False,has_copy=False,audit_ok=False):
    return (True,True,bool(has_layer),bool(has_copy),bool(has_copy and audit_ok))
def next_step(index,*,has_layer=False,has_copy=False,audit_ok=False):
    if index not in range(5): raise ValueError('Ukjent steg.')
    if index==0: return 1
    if index==1 and not has_layer: raise ValueError('Velg et QGIS-lag først.')
    if index==2 and not has_copy: raise ValueError('Lag eksportkopi først.')
    if index==3 and not audit_ok: raise ValueError('Kontrollen må bestås før eksport.')
    return min(index+1,4)
def export_is_ready(issues,audit):
    return bool(audit) and not any(i.severity=='FEIL' for i in issues)
