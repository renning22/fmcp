document.addEventListener('DOMContentLoaded', () => {
    const actionTypeSelect = document.getElementById('action-type');
    const paramsContainer = document.getElementById('params-container');
    const logStepBtn = document.getElementById('log-step-btn');
    const sequenceList = document.getElementById('sequence-list');
    const goalNameInput = document.getElementById('goal-name');
    const finishBtn = document.getElementById('finish-btn');
    const verificationModal = document.getElementById('verification-modal');
    const verificationSummary = document.getElementById('verification-summary');
    const verifyGoalName = document.getElementById('verify-goal-name');
    const verifyYesBtn = document.getElementById('verify-yes-btn');
    const verifyNoBtn = document.getElementById('verify-no-btn');
    const outcomeMessage = document.getElementById('outcome-message');

    let actionSequence = [];
    let currentParams = {}; // To store refs to current input fields

    const actionParamsConfig = {
        approve: [
            { name: 'tokenAddress', label: 'Token Address', type: 'text', placeholder: 'e.g., 0x...' },
            { name: 'spenderAddress', label: 'Spender Address', type: 'text', placeholder: 'e.g., 0x...' },
            { name: 'amount', label: 'Amount', type: 'text', placeholder: 'e.g., 1000 or MAX' }
        ],
        swap: [
            { name: 'tokenInAddress', label: 'Input Token Address', type: 'text', placeholder: 'e.g., 0x...' },
            { name: 'tokenOutAddress', label: 'Output Token Address', type: 'text', placeholder: 'e.g., 0x...' },
            { name: 'amountIn', label: 'Amount In', type: 'number', placeholder: 'e.g., 100' },
            { name: 'dexRouterAddress', label: 'DEX Router Address', type: 'text', placeholder: 'e.g., 0x...' }
        ],
        deposit: [
            { name: 'tokenAddress', label: 'Token Address', type: 'text', placeholder: 'e.g., 0x...' },
            { name: 'contractAddress', label: 'Staking Contract Address', type: 'text', placeholder: 'e.g., 0x...' },
            { name: 'amount', label: 'Amount', type: 'number', placeholder: 'e.g., 50' }
        ]
    };

    function renderParams(actionType) {
        paramsContainer.innerHTML = ''; // Clear previous params
        currentParams = {}; // Reset current params mapping
        logStepBtn.disabled = true; // Disable button until action is selected

        if (!actionType || !actionParamsConfig[actionType]) {
            return;
        }

        const params = actionParamsConfig[actionType];
        const paramGroup = document.createElement('div');

        params.forEach(param => {
            const label = document.createElement('label');
            label.setAttribute('for', `param-${param.name}`);
            label.textContent = `${param.label}:`;

            const input = document.createElement('input');
            input.setAttribute('type', param.type);
            input.setAttribute('id', `param-${param.name}`);
            input.setAttribute('placeholder', param.placeholder || '');
            if (param.type === 'number') {
                input.setAttribute('step', 'any'); // Allow decimals
            }

            paramGroup.appendChild(label);
            paramGroup.appendChild(input);
            currentParams[param.name] = input; // Store reference to the input field
        });

        paramsContainer.appendChild(paramGroup);
        logStepBtn.disabled = false; // Enable button now that params are shown
    }

    function updateSequenceDisplay() {
        sequenceList.innerHTML = '';
        actionSequence.forEach((step, index) => {
            const li = document.createElement('li');
            const paramsString = Object.entries(step.params)
                                     .map(([key, value]) => `${key}: ${value}`)
                                     .join(', ');
            li.textContent = `${index + 1}. Action: ${step.actionType}, Params: { ${paramsString} }`;
            sequenceList.appendChild(li);
        });
        finishBtn.disabled = actionSequence.length === 0; // Enable finish button if sequence has steps
    }

    function resetTraining() {
        actionSequence = [];
        updateSequenceDisplay();
        actionTypeSelect.value = '';
        paramsContainer.innerHTML = '';
        logStepBtn.disabled = true;
        goalNameInput.value = '';
        finishBtn.disabled = true;
        verificationModal.style.display = 'none';
        outcomeMessage.textContent = '';
        outcomeMessage.className = 'outcome'; // Reset outcome style
    }

    // Event Listeners
    actionTypeSelect.addEventListener('change', (e) => {
        renderParams(e.target.value);
    });

    logStepBtn.addEventListener('click', () => {
        const selectedAction = actionTypeSelect.value;
        if (!selectedAction || !currentParams) return;

        const params = {};
        let allFieldsFilled = true;
        Object.entries(currentParams).forEach(([name, inputElement]) => {
            params[name] = inputElement.value.trim();
            if (params[name] === '') {
                allFieldsFilled = false;
            }
        });

        if (!allFieldsFilled) {
            alert('Please fill in all parameter fields for the step.');
            return;
        }

        actionSequence.push({
            actionType: selectedAction,
            params: params
        });

        updateSequenceDisplay();

        // Clear param inputs but keep action selected
        Object.values(currentParams).forEach(input => input.value = '');
        // Optionally reset action selection:
        // actionTypeSelect.value = '';
        // renderParams('');
    });

    finishBtn.addEventListener('click', () => {
        const goalName = goalNameInput.value.trim();
        if (goalName === '') {
            alert('Please provide a name for this capability.');
            return;
        }
        if (actionSequence.length === 0) {
            alert('Please log at least one step before finishing.');
            return;
        }

        verifyGoalName.textContent = goalName;
        verificationSummary.textContent = actionSequence.map((step, index) => {
            const paramsString = JSON.stringify(step.params, null, 2); // Pretty print params
            return `Step ${index + 1}: ${step.actionType}
Params:
${paramsString}`;
        }).join('\n\n');

        verificationModal.style.display = 'block';
        outcomeMessage.textContent = ''; // Clear previous outcome
        outcomeMessage.className = 'outcome';
    });

    verifyYesBtn.addEventListener('click', () => {
        const goalName = goalNameInput.value.trim();
        verificationModal.style.display = 'none';
        outcomeMessage.textContent = `Success! Capability '${goalName}' created (Simulation). You can now restart training.`;
        outcomeMessage.className = 'outcome success';
        // In a real app, you'd save/register the capability here
        // For the demo, we just show success and encourage restart
         // Reset fields but keep the message
        actionSequence = [];
        updateSequenceDisplay();
        actionTypeSelect.value = '';
        paramsContainer.innerHTML = '';
        logStepBtn.disabled = true;
        goalNameInput.value = '';
        finishBtn.disabled = true;
    });

    verifyNoBtn.addEventListener('click', () => {
        verificationModal.style.display = 'none';
        outcomeMessage.textContent = 'Okay, training sequence discarded. Please restart the training process.';
        outcomeMessage.className = 'outcome error';
        resetTraining(); // Full reset
    });

    // Initial state
    resetTraining(); // Start clean
}); 