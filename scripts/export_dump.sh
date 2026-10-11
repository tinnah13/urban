#!/bin/bash
sqlite3 database/urban_mobility.db .dump > database/dump.sql
