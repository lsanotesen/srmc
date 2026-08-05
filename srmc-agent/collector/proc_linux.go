package collector

import (
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"time"
	"unicode"
)

// isProcessRunningPure checks if a process is running by reading /proc filesystem
func isProcessRunningPure(pid int) bool {
	if pid <= 0 {
		return false
	}
	procDir := fmt.Sprintf("/proc/%d", pid)
	info, err := os.Stat(procDir)
	if err != nil {
		return false
	}
	return info.IsDir()
}

// getProcessCmdline reads the command line of a process from /proc/{pid}/cmdline
func getProcessCmdline(pid int) (string, error) {
	data, err := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
	if err != nil {
		return "", err
	}
	// Replace null bytes with spaces
	cmdline := strings.ReplaceAll(string(data), "\x00", " ")
	cmdline = strings.TrimSpace(cmdline)
	return cmdline, nil
}

// getProcessCreateTime reads the process start time from /proc/{pid}/stat
// Returns the time in milliseconds since epoch
func getProcessCreateTime(pid int) (int64, error) {
	data, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if err != nil {
		return 0, err
	}

	content := string(data)
	// Extract the field after the closing parenthesis of the comm name
	// Format: pid (comm) state ppid pgrp session tty_nr tpgid flags ...
	closeParen := strings.LastIndex(content, ")")
	if closeParen == -1 {
		return 0, fmt.Errorf("cannot parse stat for pid %d", pid)
	}

	fields := strings.Fields(content[closeParen+2:])
	if len(fields) < 20 {
		return 0, fmt.Errorf("stat fields too short for pid %d", pid)
	}

	// field 20 (index 19) is starttime (in clock ticks)
	startTimeTicks, err := strconv.ParseInt(fields[19], 10, 64)
	if err != nil {
		return 0, err
	}

	// Get system boot time from /proc/stat
	bootTimeData, err := os.ReadFile("/proc/stat")
	if err != nil {
		return 0, err
	}

	var bootTime int64
	for _, line := range strings.Split(string(bootTimeData), "\n") {
		if strings.HasPrefix(line, "btime ") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				bootTime, _ = strconv.ParseInt(parts[1], 10, 64)
			}
			break
		}
	}

	if bootTime == 0 {
		return 0, fmt.Errorf("cannot read boot time")
	}

	// Get clock tick (usually 100 Hz)
	clockTick := int64(100) // default 100 Hz

	// Convert start time to Unix timestamp in milliseconds
	startTime := bootTime*1000 + (startTimeTicks*1000)/clockTick

	return startTime, nil
}

// findProcessByCmdline finds a process by matching keyword in command line
// It tries multiple matching strategies for better accuracy
func findProcessByCmdline(keyword string) int {
	if len(keyword) < 3 {
		return 0
	}

	keywordLower := strings.ToLower(keyword)
	
	// For .jar files, also try without .jar extension
	var searchKeywords []string
	searchKeywords = append(searchKeywords, keywordLower)
	
	if strings.HasSuffix(keywordLower, ".jar") {
		searchKeywords = append(searchKeywords, strings.TrimSuffix(keywordLower, ".jar"))
	} else if strings.HasSuffix(keywordLower, ".py") {
		searchKeywords = append(searchKeywords, strings.TrimSuffix(keywordLower, ".py"))
	} else if strings.HasSuffix(keywordLower, ".sh") {
		searchKeywords = append(searchKeywords, strings.TrimSuffix(keywordLower, ".sh"))
	}
	
	// Read /proc directory
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return 0
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		
		pid, err := strconv.Atoi(entry.Name())
		if err != nil {
			continue
		}

		// Skip our own process
		if pid == os.Getpid() {
			continue
		}

		// Check process status - skip zombie/dead processes
		status := getProcessStatus(pid)
		if status == "Z" || status == "X" || status == "x" || status == "unknown" {
			continue
		}

		cmdline, err := getProcessCmdline(pid)
		if err != nil {
			continue
		}

		if cmdline == "" {
			continue
		}
		
		// Skip grep, bash, sh, and other shell processes
		cmdlineLower := strings.ToLower(cmdline)
		if strings.HasPrefix(cmdlineLower, "grep ") || strings.HasPrefix(cmdlineLower, "/grep ") {
			continue
		}
		if strings.HasPrefix(cmdlineLower, "bash ") || strings.HasPrefix(cmdlineLower, "/bash ") {
			continue
		}
		if strings.HasPrefix(cmdlineLower, "sh ") || strings.HasPrefix(cmdlineLower, "/sh ") {
			continue
		}
		if strings.HasPrefix(cmdlineLower, "nohup ") || strings.HasPrefix(cmdlineLower, "/nohup ") {
			continue
		}
		
		// Check if any search keyword is in the command line
		for _, kw := range searchKeywords {
			if strings.Contains(cmdlineLower, kw) {
				// For .jar files, .py files, .sh files, direct match is sufficient
				if strings.HasSuffix(kw, ".jar") || strings.HasSuffix(kw, ".py") || strings.HasSuffix(kw, ".sh") {
					log.Printf("[DEBUG] findProcessByCmdline: found PID=%d, cmdline=%s, keyword=%s", pid, cmdline, kw)
					return pid
				}
				
				// For other keywords, verify it matches a meaningful part
				if verifyKeywordMatch(cmdlineLower, kw) {
					log.Printf("[DEBUG] findProcessByCmdline: found PID=%d, cmdline=%s, keyword=%s", pid, cmdline, kw)
					return pid
				}
			}
		}
	}

	return 0
}

// verifyKeywordMatch ensures the keyword matches a meaningful part of the command line
func verifyKeywordMatch(cmdline, keyword string) bool {
	// Split command line by spaces to get arguments
	parts := strings.Fields(cmdline)
	
	for _, part := range parts {
		partLower := strings.ToLower(part)
		// Check if the part contains the keyword
		if strings.Contains(partLower, keyword) {
			// For .jar files, check if it's an actual jar file path
			if strings.HasSuffix(keyword, ".jar") || strings.HasSuffix(partLower, ".jar") {
				return true
			}
			// For scripts, check if it's a script file
			if strings.HasSuffix(keyword, ".sh") || strings.HasSuffix(partLower, ".sh") {
				return true
			}
			if strings.HasSuffix(keyword, ".py") || strings.HasSuffix(partLower, ".py") {
				return true
			}
			// For generic executables, check if it's a filename (not just a parameter)
			if strings.Contains(partLower, keyword) {
				return true
			}
		}
	}
	
	// If keyword is not found as a separate argument, check for path-like patterns
	// (e.g., java -jar /path/to/file.jar)
	if strings.Contains(cmdline, keyword) {
		return true
	}
	
	return false
}

// getProcessStatus reads the process state from /proc/{pid}/status
func getProcessStatus(pid int) string {
	data, err := os.ReadFile(fmt.Sprintf("/proc/%d/status", pid))
	if err != nil {
		return "unknown"
	}

	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "State:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				return fields[1] // R, S, D, Z, T, etc.
			}
			break
		}
	}
	return "unknown"
}

// getCurrentUptime returns current time in milliseconds (for start time calculation)
func getCurrentTimeMs() int64 {
	return time.Now().UnixNano() / int64(time.Millisecond)
}

// isASCII checks if a string contains only ASCII characters
func isASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] > unicode.MaxASCII {
			return false
		}
	}
	return true
}
