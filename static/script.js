document.addEventListener('DOMContentLoaded', () => {
    const resumeFile = document.getElementById('resumeFile');
    const submitBtn = document.getElementById('submitBtn');
    const statusDiv = document.getElementById('status');
    const resultsDiv = document.getElementById('results');
    const scheduleTable = document.getElementById('scheduleTable');

    // Enable submit button when file is selected
    resumeFile.addEventListener('change', () => {
        submitBtn.disabled = !resumeFile.files.length;
    });

    // Handle form submission
    submitBtn.addEventListener('click', async () => {
        if (!resumeFile.files.length) return;

        submitBtn.disabled = true;
        statusDiv.textContent = 'Uploading resumes...';
        resultsDiv.classList.add('hidden');
        scheduleTable.innerHTML = '';

        try {
            const file = resumeFile.files[0];
            const resumes = JSON.parse(await file.text());
            const payload = {
                task_id: `workflow_${Date.now()}`,
                data: {
                    job_title: 'Software Engineer',
                    resumes: resumes
                }
            };

            // Start SSE for real-time updates
            const eventSource = new EventSource('/events');
            eventSource.onmessage = (event) => {
                statusDiv.textContent = event.data;
            };
            eventSource.onerror = () => {
                statusDiv.textContent = 'Processing complete.';
                eventSource.close();
            };

            // Send resumes to Host Agent
            const response = await fetch('http://localhost:8080/task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();

            if (result.error) {
                statusDiv.textContent = `Error: ${result.error}`;
                eventSource.close();
                return;
            }

            // Display schedules
            result.result.schedules.forEach(schedule => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="py-2 px-4 border">${schedule.candidate_id}</td>
                    <td class="py-2 px-4 border">${schedule.score}</td>
                    <td class="py-2 px-4 border">${schedule.interview_time}</td>
                    <td class="py-2 px-4 border">${schedule.duration}</td>
                `;
                scheduleTable.appendChild(row);
            });
            resultsDiv.classList.remove('hidden');
            statusDiv.textContent = 'Schedules generated successfully.';
            eventSource.close();
        } catch (error) {
            statusDiv.textContent = `Error: ${error.message}`;
        } finally {
            submitBtn.disabled = false;
        }
    });
});