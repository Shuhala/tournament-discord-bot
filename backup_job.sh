#!/bin/bash
PROJECT_PATH=/opt/tournament-discord-bot
cp "${PROJECT_PATH}/data/TournamentManager.db" "${PROJECT_PATH}/.backup/TournamentManager-$(date +"%m-%d-%y_%Hh%Mm%Ss").db"
