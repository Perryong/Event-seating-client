"""
Excel processing service for guest data import/export
"""

import os
import io
from typing import List, Dict, Any, Tuple
import pandas as pd
from sqlalchemy.orm import Session

from app.models import Event, Guest, Table
from app.core.db import get_db

class ExcelService:
    """Service for handling Excel operations"""
    
    REQUIRED_COLUMNS = ['name', 'table', 'seat no.', 'dietary preference']
    MAX_TABLE_SIZE = 12
    
    @staticmethod
    def create_template() -> bytes:
        """Create Excel template with required columns"""
        df = pd.DataFrame(columns=[
            'Name', 'Table', 'Seat No.', 'Dietary Preference'
        ])
        
        # Add sample data for guidance
        sample_data = [
            ['Sample Guest 1', 'A1', 1, 'none'],
            ['Sample Guest 2', 'A1', 2, 'vegetarian'],
            ['Sample Guest 3', 'B1', 1, 'halal'],
        ]
        
        for row in sample_data:
            df.loc[len(df)] = row
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Guest List')
        
        return buffer.getvalue()
    
    @staticmethod
    def validate_excel_structure(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Validate Excel file structure"""
        errors = []
        
        # Normalize column names for case-insensitive comparison
        normalized_columns = [col.lower().strip() for col in df.columns]
        required_normalized = [col.lower() for col in ExcelService.REQUIRED_COLUMNS]
        
        # Check for required columns
        missing_columns = []
        for req_col in required_normalized:
            if req_col not in normalized_columns:
                missing_columns.append(req_col)
        
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_data_constraints(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Validate data constraints like table size limits"""
        errors = []
        
        # Normalize column names
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if 'name' in col_lower:
                column_mapping['name'] = col
            elif 'table' in col_lower:
                column_mapping['table'] = col
            elif 'seat' in col_lower:
                column_mapping['seat'] = col
            elif 'dietary' in col_lower:
                column_mapping['dietary'] = col
        
        # Check table size constraints
        if 'table' in column_mapping:
            table_counts = df[column_mapping['table']].value_counts()
            oversized_tables = table_counts[table_counts > ExcelService.MAX_TABLE_SIZE]
            
            if not oversized_tables.empty:
                for table_name, count in oversized_tables.items():
                    errors.append(f"Table '{table_name}' has {count} guests (max {ExcelService.MAX_TABLE_SIZE})")
        
        # Validate seat numbers are numeric
        if 'seat' in column_mapping:
            try:
                pd.to_numeric(df[column_mapping['seat']], errors='raise')
            except (ValueError, TypeError):
                errors.append("Seat numbers must be numeric")
        
        # Check for duplicate seats within same table
        if 'table' in column_mapping and 'seat' in column_mapping:
            duplicates = df.groupby([column_mapping['table'], column_mapping['seat']]).size()
            duplicate_seats = duplicates[duplicates > 1]
            
            if not duplicate_seats.empty:
                for (table, seat), count in duplicate_seats.items():
                    errors.append(f"Duplicate seat {seat} in table '{table}' ({count} times)")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def process_excel_upload(
        file_content: bytes, 
        event_id: int, 
        db: Session
    ) -> Tuple[bool, List[str], int]:
        """Process uploaded Excel file and update database"""
        try:
            # Read Excel file
            df = pd.read_excel(io.BytesIO(file_content))
            
            # Validate structure
            valid_structure, structure_errors = ExcelService.validate_excel_structure(df)
            if not valid_structure:
                return False, structure_errors, 0
            
            # Validate data constraints
            valid_data, data_errors = ExcelService.validate_data_constraints(df)
            if not valid_data:
                return False, data_errors, 0
            
            # Create column mapping
            column_mapping = {}
            for col in df.columns:
                col_lower = col.lower().strip()
                if 'name' in col_lower:
                    column_mapping['name'] = col
                elif 'table' in col_lower:
                    column_mapping['table'] = col
                elif 'seat' in col_lower:
                    column_mapping['seat'] = col
                elif 'dietary' in col_lower:
                    column_mapping['dietary'] = col
            
            # Clear existing guests for this event
            db.query(Guest).filter(Guest.event_id == event_id).delete()
            db.query(Table).filter(Table.event_id == event_id).delete()
            
            # Process data
            processed_count = 0
            tables_created = set()
            
            for _, row in df.iterrows():
                # Skip empty rows
                if pd.isna(row[column_mapping['name']]) or str(row[column_mapping['name']]).strip() == '':
                    continue
                
                table_name = str(row[column_mapping['table']]).strip()
                
                # Create table if not exists
                if table_name not in tables_created:
                    table = Table(
                        event_id=event_id,
                        table_name=table_name
                    )
                    db.add(table)
                    tables_created.add(table_name)
                
                # Normalize dietary preference
                dietary = str(row[column_mapping['dietary']]).lower().strip()
                if dietary in ['', 'nan', 'none']:
                    dietary = 'none'
                elif dietary in ['vegetarian', 'veg']:
                    dietary = 'vegetarian'
                elif dietary in ['halal']:
                    dietary = 'halal'
                elif 'allerg' in dietary:
                    dietary = f"allergies:{dietary}"
                
                # Create guest
                guest = Guest(
                    event_id=event_id,
                    name=str(row[column_mapping['name']]).strip(),
                    table_name=table_name,
                    seat_no=int(row[column_mapping['seat']]),
                    dietary=dietary,
                    checked_in=False
                )
                db.add(guest)
                processed_count += 1
            
            db.commit()
            return True, [], processed_count
            
        except Exception as e:
            db.rollback()
            return False, [f"Error processing Excel file: {str(e)}"], 0
    
    @staticmethod
    def export_current_data(event_id: int, db: Session, include_checkin: bool = True) -> bytes:
        """Export current guest data to Excel"""
        guests = db.query(Guest).filter(Guest.event_id == event_id).all()
        
        data = []
        for guest in guests:
            row = {
                'Name': guest.name,
                'Table': guest.table_name,
                'Seat No.': guest.seat_no,
                'Dietary Preference': guest.dietary
            }
            if include_checkin:
                row['Checked In'] = 'Yes' if guest.checked_in else 'No'
            
            data.append(row)
        
        df = pd.DataFrame(data)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Guest List')
        
        return buffer.getvalue()
    
    @staticmethod
    def save_original_file(file_content: bytes, event_id: int) -> str:
        """Save original uploaded file"""
        upload_dir = f"uploads/{event_id}"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = f"{upload_dir}/original.xlsx"
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return file_path
