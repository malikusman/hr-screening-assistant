document.addEventListener('DOMContentLoaded', () => {
    const resumeFile = document.getElementById('resumeFile');
    const submitBtn = document.getElementById('submitBtn');
    const statusDiv = document.getElementById('status');
    const statusText = statusDiv.querySelector('span');
    const spinner = document.getElementById('spinner');
    const resultsDiv = document.getElementById('results');
    const scheduleTable = document.getElementById('scheduleTable');

    // Enable submit button when file is selected
    resumeFile.addEventListener('change', () => {
        submitBtn.disabled = !resumeFile.files.length;
        statusText.textContent = resumeFile.files.length ? 'Ready to process!' : 'Waiting for upload...';
    });

    // Handle form submission
    submitBtn.addEventListener('click', async () => {
        if (!resumeFile.files.length) return;

        submitBtn.disabled = true;
        statusText.textContent = 'Uploading resumes...';
        spinner.classList.remove('hidden');
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
                statusText.textContent = event.data;
            };
            eventSource.onerror = () => {
                statusText.textContent = 'Processing complete.';
                spinner.classList.add('hidden');
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
                statusText.textContent = `Error: ${result.error}`;
                spinner.classList.add('hidden');
                eventSource.close();
                return;
            }

            // Display schedules
            result.result.schedules.forEach(schedule => {
                const row = document.createElement('tr');
                row.classList.add('hover:bg-gray-50', 'transition');
                row.innerHTML = `
                    <td class="py-3 px-6 border-b">${schedule.candidate_id}</td>
                    <td class="py-3 px-6 border-b">${schedule.score}</td>
                    <td class="py-3 px-6 border-b">${schedule.interview_time}</td>
                    <td class="py-3 px-6 border-b">${schedule.duration}</td>
                `;
                scheduleTable.appendChild(row);
            });
            resultsDiv.classList.remove('hidden');
            statusText.textContent = 'Schedules generated successfully!';
            spinner.classList.add('hidden');
            eventSource.close();
        } catch (error) {
            statusText.textContent = `Error: ${error.message}`;
            spinner.classList.add('hidden');
        } finally {
            submitBtn.disabled = false;
        }
    });
});