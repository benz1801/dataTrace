import pandas as pd
import numpy as np

# Create a dummy dataframe for testing
df = pd.DataFrame({
    'id': range(1, 101),
    'category': np.random.choice(['A', 'B', 'C'], 100),
    'value': np.random.randn(100) * 100,
    'status': np.random.choice(['active', 'inactive'], 100)
})

# Add some missing values for testing dropna
df.loc[10:20, 'value'] = np.nan

df.to_csv('test_data.csv', index=False)
print("Test data created successfully.")
