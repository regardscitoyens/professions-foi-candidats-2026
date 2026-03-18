#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, shutil
import re, time
import csv, json
import requests
from seleniumbase import SB

HOSTURL = 'https://programme-candidats.interieur.gouv.fr/'
URLS = {
    "DP21": HOSTURL + "elections-departementales-2021/",
    "RG21": HOSTURL + "elections-regionales-2021/",
    "LG22": HOSTURL + "elections-legislatives-2022/",
    "LG24": HOSTURL + "elections-legislatives-2024/",
    "MN26": HOSTURL + "elections-municipales-2026/",
    "MN26ARR": HOSTURL + "elections-arrondissements-2026/",
    "MN26MET": HOSTURL + "elections-metropolitaines-2026/"
}


def downloadPDF(eldir, filename, url, retries=3):
    filepath = os.path.join(eldir, "%s.pdf" % filename)
    if os.path.exists(filepath):
        #print("WARNING: already existing PDF", filepath, file=sys.stderr)
        return False
    try:
        r = requests.get(url, stream=True)
        r.raw.decode_content = True
        with open(filepath, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
        return True
    except Exception as e:
        if retries:
            time.sleep(2)
            return downloadPDF(eldir, filename, url, retries - 1)
        print("WARNING: could not download %s for" % url, filename, file=sys.stderr)
        print("%s:" % type(e), e, file=sys.stderr)
        return False


def request_data(sb, url, field, fallback_field=None, retries=10, allow_fail=False):
    jsonurl = "%s.json?_=%s" % (url, time.time())
    #print("CALL %s" % jsonurl)
    try:
        sb.uc_open_with_reconnect(jsonurl, 10/retries)
        sb.sleep(10/retries)
        content = sb.get_page_source().replace('<html><head><meta name="color-scheme" content="light dark"><meta charset="utf-8"></head><body><pre>', '').replace('</pre><div class="json-formatter-container"></div></body></html>', '')
        #print('CONTENT: "%s"' % content)
        jsondata = json.loads(content)
        if field in jsondata:
            return jsondata[field]
        return jsondata[fallback_field]
    except Exception as e:
        if allow_fail:
            print("Data from %s not available yet, skipping it" % jsonurl, file=sys.stderr)
            print(type(e), e, file=sys.stderr)
            return []
        if retries:
            time.sleep(30/retries)
            return request_data(sb, url, field, fallback_field=fallback_field, retries = retries - 1)
        print("ERROR: impossible to get %s list at" % field, jsonurl, file=sys.stderr)
        print("%s:" % type(e), e, file=sys.stderr)
        sys.exit(1)


def scrape_municipales(elcode="MN26"):
  with SB(uc=True) as sb:
    eldir = os.path.join("documents", elcode)
    if not os.path.exists(eldir):
        os.makedirs(eldir)
    for tour in [1, 2]:
        nb_dep = 0
        nb_com = 0
        nb_c = 0
        nb_d = 0
        nb_n = 0
        url = URLS[elcode] + "data-json/%s_departements" % tour
        data = {}
        for dept in request_data(sb, url, "data", allow_fail=True):
            nb_dep += 1
            depcode = dept["id"]
            depname = dept["name"]
            depurl = URLS[elcode] + "data-json/%s_communes_dpt_%s" % (tour, depcode)
            data[depcode] = {
                "name": depname,
                "url": depurl,
                "communes": {}
            }
            deptdir = os.path.join(eldir, depcode)
            if not os.path.exists(deptdir):
                os.makedirs(deptdir)
            for commune in request_data(sb, depurl, "data"):
                nb_com += 1
                comcode = commune["id"]
                comname = commune["com"]
                comurl = URLS[elcode] + "data-json/%s_candidats_com_%s" % (tour, comcode)
                data[depcode]["communes"][comcode] = {
                    "name": comname,
                    "url": comurl,
                    "candidats": request_data(sb, comurl, "data")
                }
                comdir = os.path.join(deptdir, comcode)
                if not os.path.exists(comdir):
                    os.makedirs(comdir)
                for candidat in data[depcode]["communes"][comcode]["candidats"]:
                    nb_c += 1
                    name = candidat["candidat"].replace(" ", "_")
                    codeId = "%s-%s-%s-%s-%s-tour%s-" % (elcode, depcode, comcode, name, candidat["numPanneau"], tour)
                    pdf = candidat["pdf_acc"] if candidat["pdf_acc"] != "0" else candidat["pdf"]
                    if pdf != "0":
                        nb_d += 1
                        nb_n += downloadPDF(comdir, codeId + "profession_foi", URLS[elcode] + "data-pdf/%s.pdf" % pdf)
                    falc = candidat["falc_acc"] if candidat["falc_acc"] != "0" else candidat["falc"]
                    if falc != "0":
                        nb_n += downloadPDF(comdir, codeId + "profession_foi_falc", URLS[elcode] + "data-pdf/%s.pdf" % falc)

        with open(os.path.join(eldir, "%s-tour%s-metadata.json" % (elcode, tour)), "w") as f:
            json.dump(data, f, indent=2)
        if nb_n:
            print("%s tour %s: %s new documents collected (%s total candidates are published out of %s listed in %s departments and %s communes)." % (elcode, tour, nb_n, nb_d, nb_c, nb_dep, nb_com))

def scrape_municipales_arrondissements(elcode="MN26ARR"):
  with SB(uc=True) as sb:
    eldir = os.path.join("documents", elcode)
    if not os.path.exists(eldir):
        os.makedirs(eldir)
    for tour in [1, 2]:
        nb_com = 0
        nb_sec = 0
        nb_c = 0
        nb_d = 0
        nb_n = 0
        url = URLS[elcode] + "data-json/%s_communes" % tour
        data = {}
        for commune in request_data(sb, url, "data", allow_fail=True):
            nb_com += 1
            comcode = commune["id"]
            comname = commune["name"]
            comurl = URLS[elcode] + "data-json/%s_sects_com_%s" % (tour, comcode)
            data[comcode] = {
                "name": comname,
                "url": comurl,
                "secteurs": {}
            }
            comdir = os.path.join(eldir, comcode)
            if not os.path.exists(comdir):
                os.makedirs(comdir)
            for sect in request_data(sb, comurl, "data"):
                nb_sec += 1
                seccode = sect["id"]
                secname = sect["sect"]
                securl = URLS[elcode] + "data-json/%s_candidats_sect_%s" % (tour, seccode)
                data[comcode]["secteurs"][seccode] = {
                    "name": secname,
                    "url": securl,
                    "candidats": request_data(sb, securl, "data")
                }
                secdir = os.path.join(comdir, seccode)
                if not os.path.exists(secdir):
                    os.makedirs(secdir)
                for candidat in data[comcode]["secteurs"][seccode]["candidats"]:
                    nb_c += 1
                    name = candidat["candidat"].replace(" ", "_")
                    codeId = "%s-%s-%s-%s-%s-tour%s-" % (elcode, comcode, seccode, name, candidat["numPanneau"], tour)
                    pdf = candidat["pdf_acc"] if candidat["pdf_acc"] != "0" else candidat["pdf"]
                    if pdf != "0":
                        nb_d += 1
                        nb_n += downloadPDF(secdir, codeId + "profession_foi", URLS[elcode] + "data-pdf/%s.pdf" % pdf)
                    falc = candidat["falc_acc"] if candidat["falc_acc"] != "0" else candidat["falc"]
                    if falc != "0":
                        nb_n += downloadPDF(secdir, codeId + "profession_foi_falc", URLS[elcode] + "data-pdf/%s.pdf" % falc)

        with open(os.path.join(eldir, "%s-tour%s-metadata.json" % (elcode, tour)), "w") as f:
            json.dump(data, f, indent=2)
        if nb_n:
            print("%s tour %s: %s new documents collected (%s total candidates are published out of %s listed in %s communes and %s arrondissements)." % (elcode, tour, nb_n, nb_d, nb_c, nb_com, nb_sec))

def scrape_municipales_metropole(elcode="MN26MET"):
  with SB(uc=True) as sb:
    eldir = os.path.join("documents", elcode)
    if not os.path.exists(eldir):
        os.makedirs(eldir)
    for tour in [1, 2]:
        nb_circo = 0
        nb_c = 0
        nb_d = 0
        nb_n = 0
        url = URLS[elcode] + "data-json/%s_circonscriptions" % tour
        data = {}
        for circo in request_data(sb, url, "data", allow_fail=True):
            nb_circo += 1
            circocode = circo["codeCirco"]
            circoname = circo["circo"]
            circourl = URLS[elcode] + "data-json/%s_candidats_circo_%s" % (tour, circocode)
            data[circocode] = {
                "name": circoname,
                "url": circourl,
                "candidats": request_data(sb, circourl, "data")
            }
            circodir = os.path.join(eldir, circocode)
            if not os.path.exists(circodir):
                os.makedirs(circodir)
            for candidat in data[circocode]["candidats"]:
                nb_c += 1
                name = candidat["candidat"].replace(" ", "_")
                codeId = "%s-%s-%s-%s-tour%s-" % (elcode, circocode, name, candidat["numPanneau"], tour)
                pdf = candidat["pdf_acc"] if candidat["pdf_acc"] != "0" else candidat["pdf"]
                if pdf != "0":
                    nb_d += 1
                    nb_n += downloadPDF(circodir, codeId + "profession_foi", URLS[elcode] + "data-pdf/%s.pdf" % pdf)
                falc = candidat["falc_acc"] if candidat["falc_acc"] != "0" else candidat["falc"]
                if falc != "0":
                    nb_n += downloadPDF(circodir, codeId + "profession_foi_falc", URLS[elcode] + "data-pdf/%s.pdf" % falc)

        with open(os.path.join(eldir, "%s-tour%s-metadata.json" % (elcode, tour)), "w") as f:
            json.dump(data, f, indent=2)
        if nb_n:
            print("%s tour %s: %s new documents collected (%s total candidates are published out of %s listed in %s circonscriptions)." % (elcode, tour, nb_n, nb_d, nb_c, nb_circo))


if __name__ == '__main__':
    election = ""
    if len(sys.argv) > 1:
        election = sys.argv[1]
    if election.startswith("MN"):
        scrape_municipales(election)
        scrape_municipales_arrondissements(election + "ARR")
        scrape_municipales_metropole(election + "MET")
