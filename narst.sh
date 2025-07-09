#!/bin/bash
CONFIG_FILE="narst_config.json"

list_proxies() {
    echo "Available Proxy Servers:"
    jq -r '.proxies[]' "$CONFIG_FILE" | sed 's/^/ - /'
}

list_web_servers() {
    echo "Available Web Servers:"
    jq -r '.web_servers[]' "$CONFIG_FILE" | sed 's/^/ - /'
}

if [[ "$1" == "--proxy-list" ]]; then
    list_proxies
    exit 0
fi

if [[ "$1" == "--web-list" ]]; then
    list_web_servers
    exit 0
fi

if [[ "$1" == "-p" && "$3" == "-w" ]]; then
    PROXY="$2"
    WEB="$4"

    echo "Selected Proxy Server: $PROXY"
    echo "Selected Web Server: $WEB"

    COMPOSE_FILE="docker/${PROXY}-${WEB}.yml"
    echo "📦 Using docker-compose file: $COMPOSE_FILE"

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        echo "❌ Error: Compose file $COMPOSE_FILE not found."
        exit 1
    fi

    docker-compose -f "$COMPOSE_FILE" up --build -d

    echo "⏳ Waiting for services to initialize..."
    sleep 5

    echo "🚀 Running attack..."
    ATTACK_OUTPUT=$(python3 script/attack_runner.py http://localhost:8080)
    echo "$ATTACK_OUTPUT"

    # Determine if any attack succeeded
    if echo "$ATTACK_OUTPUT" | grep -qE "🚨|⚠"; then
        POISONING=1
        DETECTION_RESULT=$(echo "$ATTACK_OUTPUT" | grep "➤ Detection result: Likely" | tail -n1 | sed 's/.*Likely //')
    else
        POISONING=0
        DETECTION_RESULT=""
    fi

    CSV_FILE="attack_results.csv"
    if [[ ! -f "$CSV_FILE" ]]; then
        echo "proxy,backend,detection,poisoning" > "$CSV_FILE"
    fi
    echo "$PROXY,$WEB,$DETECTION_RESULT,$POISONING" >> "$CSV_FILE"

    echo -e "\n📝 Result stored to $CSV_FILE"
    echo -e "Proxy: $PROXY\nBackend: $WEB\nDetection: ${DETECTION_RESULT:-N/A}\nPoisoning: $POISONING"

    echo "🧹 Cleaning up..."
    docker-compose -f "$COMPOSE_FILE" down -v > /dev/null

    exit 0
fi


if [[ "$1" == "--health-check" ]]; then
    PROXIES=($(jq -r '.proxies[]' "$CONFIG_FILE"))
    WEB_SERVERS=($(jq -r '.web_servers[]' "$CONFIG_FILE"))

    for proxy in "${PROXIES[@]}"; do
        for web in "${WEB_SERVERS[@]}"; do
            combo_file="docker/${proxy}-${web}.yml"
            echo -e "\n🔍 Testing combo: $proxy → $web"

            if [[ ! -f "$combo_file" ]]; then
                echo "⚠️  Missing config: $combo_file — Skipping"
                continue
            fi

            docker-compose -f "$combo_file" up --build -d >/dev/null 2>&1
            sleep 5

            if curl -s --max-time 5 http://localhost:8080 >/dev/null; then
                echo "✅ SUCCESS: $proxy → $web"
            else
                echo "❌ FAIL: $proxy → $web"
            fi

            docker-compose -f "$combo_file" down -v >/dev/null 2>&1
        done
    done
    exit 0
fi

if [[ "$1" == "--attack-all" ]]; then
    SECONDS=0
    CSV_FILE="attack_results.csv"
    [[ -f "$CSV_FILE" ]] && rm "$CSV_FILE"
    echo "proxy,backend,detection,poisoning" > "$CSV_FILE"

    PROXIES=$(jq -r '.proxies[]' "$CONFIG_FILE")
    WEB_SERVERS=$(jq -r '.web_servers[]' "$CONFIG_FILE")

    for proxy in $PROXIES; do
        for web in $WEB_SERVERS; do
            combo_file="docker/${proxy}-${web}.yml"
            echo -e "\n🔍 Testing attack: $proxy → $web"

            if [[ ! -f "$combo_file" ]]; then
                echo "⚠  Missing config: $combo_file — Skipping"
                continue
            fi

            docker-compose -f "$combo_file" up --build -d >/dev/null 2>&1
            sleep 5

            echo "🚀 Running attack..."
            ATTACK_OUTPUT=$(python3 script/attack_runner.py http://localhost:8080)
            echo "$ATTACK_OUTPUT"

            if echo "$ATTACK_OUTPUT" | grep -qE "🚨|⚠"; then
                POISONING=1
                DETECTION_RESULT=$(echo "$ATTACK_OUTPUT" | grep "➤ Detection result: Likely" | tail -n1 | sed 's/.*Likely //')
            else
                POISONING=0
                DETECTION_RESULT=""
            fi

            echo "$proxy,$web,$DETECTION_RESULT,$POISONING" >> "$CSV_FILE"
            echo -e "📌 $proxy → $web | Detection: ${DETECTION_RESULT:-N/A} | Poisoning: $POISONING"

            docker-compose -f "$combo_file" down -v >/dev/null 2>&1
        done
    done

    # ─── end timer & print ──────────────────────────
    DURATION=$SECONDS
    # format as H:M:S if you like:
    hours=$(( DURATION/3600 ))
    mins=$(( (DURATION%3600)/60 ))
    secs=$(( DURATION%60 ))

    echo -e "\n📄 All results saved to $CSV_FILE"
    printf "⏱ Total elapsed time: %02d:%02d:%02d (hh:mm:ss)\n" "$hours" "$mins" "$secs"
    exit 0
fi

if [[ "$1" == "--demo" ]]; then
    SECONDS=0
    DEMO_DIR="CVE-2019-18277"
    echo "🚧 Launching CVE-2019-18277 demo environment..."

    docker-compose -f "$DEMO_DIR/docker-compose.yml" up --build -d
    echo "⏳ Waiting for CVE containers to initialize..."
    sleep 5

    echo "🚀 Running attack on http://localhost:9013"
    python3 script/attack_runner.py http://localhost:9013

    echo "🧹 Cleaning up CVE demo containers..."
    docker-compose -f "$DEMO_DIR/docker-compose.yml" down -v > /dev/null

    DURATION=$SECONDS
    # format as H:M:S if you like:
    hours=$(( DURATION/3600 ))
    mins=$(( (DURATION%3600)/60 ))
    secs=$(( DURATION%60 ))

    printf "⏱ Total elapsed time: %02d:%02d:%02d (hh:mm:ss)\n" "$hours" "$mins" "$secs"

    exit 0
fi

# ──────────────────────────────────────────────────────────────────────────────
# Insert this at the very end of narst.sh, just before the final "Usage:" block.

if [[ "$1" == "--measure-accuracy" ]]; then
  RUNS=100
  # Adjust path if your payloads.json lives elsewhere
  PAYLOAD_COUNT=$(jq -r '.permute | length' payloads/payloads.json)
  TOTAL_COMPARISONS=$(( (RUNS - 1) * PAYLOAD_COUNT ))

  OUT_CSV="accuracy_runs.csv"
  echo "run,detected,not_detected,error" > "$OUT_CSV"

  declare -A CLASS

  for run in $(seq 1 $RUNS); do
    echo "🔁 Starting run $run of $RUNS…"
    RAW=$(./narst.sh --demo)

    DETECTED=$(grep -c '!!! POTENTIAL REQUEST SMUGGLING DETECTED' <<<"$RAW")
    ERRORS=$(grep -E -c 'Error during second request|timed out' <<<"$RAW")
    TOTAL_DONE=$(grep -cE '^======== Testing Payload Type:' <<<"$RAW")
    NOT_DETECTED=$(( TOTAL_DONE - DETECTED - ERRORS ))

    echo "$run,$DETECTED,$NOT_DETECTED,$ERRORS" >> "$OUT_CSV"

    idx=0
    while IFS= read -r line; do
      if [[ "$line" == ========\ Testing\ Payload\ Type:* ]]; then
        ((idx++))
        # grab the next few lines to classify
        start=$(grep -n -m1 -F "$line" <<<"$RAW" | cut -d: -f1)
        block=$(printf '%s\n' "$RAW" | tail -n +"$start" | head -n5)

        if grep -q '!!! POTENTIAL REQUEST SMUGGLING DETECTED' <<<"$block"; then
          CLASS["$run,$idx"]="D"
        elif grep -q 'Normal GET request did NOT receive 200 OK' <<<"$block"; then
          CLASS["$run,$idx"]="N"
        else
          CLASS["$run,$idx"]="E"
        fi
      fi
    done <<<"$RAW"
  done

  AGREEMENTS=0
  for run in $(seq 1 $RUNS); do
    (( run == 2 )) && continue
    for idx in $(seq 1 $PAYLOAD_COUNT); do
      [[ "${CLASS["$run,$idx"]}" == "${CLASS["2,$idx"]}" ]] && ((AGREEMENTS++))
    done
  done

  CONSISTENCY=$(awk -v a=$AGREEMENTS -v t=$TOTAL_COMPARISONS \
    'BEGIN{printf("%.2f%%",100*a/t)}')

  echo
  echo "📊 Final Results over $RUNS runs and $PAYLOAD_COUNT payloads:"
  echo "  Total comparisons        : $TOTAL_COMPARISONS"
  echo "  Agreements with run #2   : $AGREEMENTS"
  echo "  Consistency (accuracy)   : $CONSISTENCY"
  echo
  exit 0
fi
# ──────────────────────────────────────────────────────────────────────────────


echo "Usage:"
echo "  ./narst.sh --proxy-list          List available proxy servers"
echo "  ./narst.sh --web-list            List available web servers"
echo "  ./narst.sh -p <proxy> -w <web>   Set up specified proxy to web backend"
echo "  ./narst.sh --health-check        Health Check"
echo "  ./narst.sh --attack-all          Run attack on all valid combos and save results"
echo "  ./narst.sh --demo                Demo on Vulnerable Servers"
exit 1
