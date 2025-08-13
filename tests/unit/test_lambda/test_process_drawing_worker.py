import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lambda_functions.process_drawing_worker import handler, process_job


class TestProcessDrawingWorkerLambda:
    """Test cases for the process_drawing_worker Lambda function."""

    @pytest.fixture
    def mock_sqs_event(self):
        """Create a mock SQS event with a job message."""
        return {
            'Records': [
                {
                    'body': json.dumps({
                        'job_id': 'job_1234567890',
                        'company_client_job': '7central#test_client#job_1234567890',
                        'drawing_s3_key': '7central/test_client/test_project/job_1234567890/drawing.pdf',
                        'context_s3_key': None,
                        'context_text': None,
                        'pipeline_config': 'full_analysis',
                        'client_name': 'Test Client',
                        'project_name': 'Test Project',
                        'created_at': 1640995200
                    }),
                    'messageId': 'test-message-id',
                    'receiptHandle': 'test-receipt-handle'
                }
            ]
        }

    @pytest.fixture
    def mock_lambda_context(self):
        """Create a mock Lambda context."""
        context = MagicMock()
        context.get_remaining_time_in_millis.return_value = 300000  # 5 minutes
        return context

    @pytest.fixture
    def mock_pdf_content(self):
        """Mock PDF file content."""
        return b'%PDF-1.4\n%mock PDF content with security components\n%%EOF'

    @patch('src.lambda_functions.process_drawing_worker.StorageManager')
    def test_successful_job_processing(self, mock_storage_manager, mock_sqs_event, mock_lambda_context, mock_pdf_content):
        """Test successful end-to-end job processing."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        
        # Mock file retrieval
        mock_storage.get_file.return_value = mock_pdf_content
        mock_storage.save_job_status.return_value = None
        
        # Mock agents
        with patch('src.lambda_functions.process_drawing_worker.PDFProcessor') as mock_pdf_processor, \
             patch('src.lambda.process_drawing_worker.ScheduleAgentV2') as mock_schedule_agent, \
             patch('src.lambda.process_drawing_worker.ExcelGenerationAgent') as mock_excel_agent, \
             patch('src.lambda.process_drawing_worker.JudgeAgentV2') as mock_judge_agent:
            
            # Mock PDF processor
            mock_processor_instance = mock_pdf_processor.return_value
            mock_metadata = MagicMock()
            mock_metadata.total_pages = 2
            mock_metadata.pdf_type.value = 'text_based'
            mock_processor_instance.extract_metadata.return_value = mock_metadata
            mock_processor_instance.process_pdf.return_value = ([MagicMock()], None)
            
            # Mock schedule agent
            mock_schedule_instance = mock_schedule_agent.return_value
            mock_schedule_instance.process.return_value = {
                'components': {
                    'pages': [
                        {'components': [{'type': 'door', 'id': 'D1'}]},
                        {'components': [{'type': 'window', 'id': 'W1'}]}
                    ]
                }
            }
            
            # Mock Excel agent
            mock_excel_instance = mock_excel_agent.return_value
            mock_excel_instance.process.return_value = {
                'status': 'completed',
                'file_path': 'path/to/excel.xlsx',
                'summary': {'total_components': 2}
            }
            
            # Mock Judge agent
            mock_judge_instance = mock_judge_agent.return_value
            mock_judge_instance.process.return_value = {
                'evaluation': {
                    'overall_assessment': 'Good',
                    'completeness': 85.0,
                    'correctness': 90.0
                }
            }
            
            # Act
            result = handler(mock_sqs_event, mock_lambda_context)
            
            # Assert
            assert result['statusCode'] == 200
            
            response_body = json.loads(result['body'])
            assert response_body['processed_records'] == 1
            assert len(response_body['results']) == 1
            assert response_body['results'][0]['status'] == 'completed'
            
            # Verify storage operations
            assert mock_storage.get_file.call_count >= 1
            assert mock_storage.save_job_status.call_count >= 3  # Multiple status updates

    @patch('src.lambda_functions.process_drawing_worker.StorageManager')
    def test_pdf_processing_error(self, mock_storage_manager, mock_sqs_event, mock_lambda_context):
        """Test handling of PDF processing errors."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        
        from src.utils.pdf_processor import CorruptedPDFError
        mock_storage.get_file.side_effect = CorruptedPDFError("PDF is corrupted")
        
        # Act
        result = handler(mock_sqs_event, mock_lambda_context)
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert response_body['processed_records'] == 1
        assert response_body['results'][0]['status'] == 'failed'
        
        # Verify job status was updated to failed
        mock_storage.save_job_status.assert_called()

    @patch('src.lambda_functions.process_drawing_worker.StorageManager')
    def test_schedule_agent_error(self, mock_storage_manager, mock_sqs_event, mock_lambda_context, mock_pdf_content):
        """Test handling of Schedule Agent errors."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_file.return_value = mock_pdf_content
        
        with patch('src.lambda_functions.process_drawing_worker.PDFProcessor') as mock_pdf_processor, \
             patch('src.lambda.process_drawing_worker.ScheduleAgentV2') as mock_schedule_agent:
            
            # Mock PDF processor success
            mock_processor_instance = mock_pdf_processor.return_value
            mock_metadata = MagicMock()
            mock_metadata.total_pages = 1
            mock_metadata.pdf_type.value = 'text_based'
            mock_processor_instance.extract_metadata.return_value = mock_metadata
            mock_processor_instance.process_pdf.return_value = ([MagicMock()], None)
            
            # Mock schedule agent failure
            from src.agents.schedule_agent_v2 import ScheduleAgentError
            mock_schedule_instance = mock_schedule_agent.return_value
            mock_schedule_instance.process.side_effect = ScheduleAgentError("Rate limit exceeded")
            
            # Act
            result = handler(mock_sqs_event, mock_lambda_context)
            
            # Assert
            assert result['statusCode'] == 200
            
            response_body = json.loads(result['body'])
            assert response_body['results'][0]['status'] == 'failed'

    @patch('src.lambda_functions.process_drawing_worker.StorageManager')
    def test_timeout_detection(self, mock_storage_manager, mock_sqs_event, mock_pdf_content):
        """Test Lambda timeout detection and graceful handling."""
        
        # Arrange
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_file.return_value = mock_pdf_content
        
        # Create context with very short remaining time
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 30000  # 30 seconds (less than buffer)
        
        with patch('src.lambda_functions.process_drawing_worker.PDFProcessor') as mock_pdf_processor:
            mock_processor_instance = mock_pdf_processor.return_value
            mock_metadata = MagicMock()
            mock_metadata.total_pages = 1
            mock_metadata.pdf_type.value = 'text_based'
            mock_processor_instance.extract_metadata.return_value = mock_metadata
            mock_processor_instance.process_pdf.return_value = ([MagicMock()], None)
            
            # Act
            result = handler(mock_sqs_event, mock_context)
            
            # Assert
            assert result['statusCode'] == 200
            
            # Verify timeout was handled gracefully
            mock_storage.save_job_status.assert_called()
            # Check that timeout_detected flag was set
            call_args = mock_storage.save_job_status.call_args_list
            timeout_update_found = any(
                'timeout_detected' in str(call_args) for call_args in call_args
            )
            assert timeout_update_found

    @patch('src.lambda_functions.process_drawing_worker.StorageManager')
    def test_context_processing(self, mock_storage_manager, mock_pdf_content):
        """Test context file processing in the worker."""
        
        # Arrange
        event_with_context = {
            'Records': [
                {
                    'body': json.dumps({
                        'job_id': 'job_1234567890',
                        'company_client_job': '7central#test_client#job_1234567890',
                        'drawing_s3_key': '7central/test_client/test_project/job_1234567890/drawing.pdf',
                        'context_s3_key': '7central/test_client/test_project/job_1234567890/context.docx',
                        'context_text': None,
                        'pipeline_config': 'full_analysis',
                        'client_name': 'Test Client',
                        'project_name': 'Test Project',
                        'created_at': 1640995200
                    })
                }
            ]
        }
        
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000
        
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        
        # Mock file retrieval for both drawing and context
        mock_storage.get_file.side_effect = [
            mock_pdf_content,  # Drawing file
            b'mock docx content'  # Context file
        ]
        
        with patch('src.lambda_functions.process_drawing_worker.PDFProcessor') as mock_pdf_processor, \
             patch('src.lambda.process_drawing_worker.ContextAgent') as mock_context_agent, \
             patch('src.lambda.process_drawing_worker.ScheduleAgentV2') as mock_schedule_agent, \
             patch('src.lambda.process_drawing_worker.ExcelGenerationAgent') as mock_excel_agent, \
             patch('src.lambda.process_drawing_worker.JudgeAgentV2') as mock_judge_agent:
            
            # Mock all agents for success
            mock_processor_instance = mock_pdf_processor.return_value
            mock_metadata = MagicMock()
            mock_metadata.total_pages = 1
            mock_metadata.pdf_type.value = 'text_based'
            mock_processor_instance.extract_metadata.return_value = mock_metadata
            mock_processor_instance.process_pdf.return_value = ([MagicMock()], None)
            
            mock_context_instance = mock_context_agent.return_value
            mock_context_instance.process.return_value = {'context': 'processed context'}
            
            mock_schedule_instance = mock_schedule_agent.return_value
            mock_schedule_instance.process.return_value = {
                'components': {'pages': [{'components': []}]}
            }
            
            mock_excel_instance = mock_excel_agent.return_value
            mock_excel_instance.process.return_value = {'status': 'completed'}
            
            mock_judge_instance = mock_judge_agent.return_value
            mock_judge_instance.process.return_value = {'evaluation': {}}
            
            # Act
            result = handler(event_with_context, mock_context)
            
            # Assert
            assert result['statusCode'] == 200
            
            # Verify both files were retrieved
            assert mock_storage.get_file.call_count == 2
            
            # Verify context agent was called
            mock_context_instance.process.assert_called_once()

    def test_malformed_sqs_message(self):
        """Test handling of malformed SQS messages."""
        
        # Arrange
        malformed_event = {
            'Records': [
                {
                    'body': 'invalid json',
                    'messageId': 'test-message-id'
                }
            ]
        }
        
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000
        
        # Act
        result = handler(malformed_event, mock_context)
        
        # Assert
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert response_body['processed_records'] == 1
        assert response_body['results'][0]['status'] == 'failed'
        assert 'error' in response_body['results'][0]

    @patch('src.lambda_functions.process_drawing_worker.StorageManager')
    def test_multiple_records_processing(self, mock_storage_manager, mock_pdf_content):
        """Test processing multiple SQS records in one invocation."""
        
        # Arrange
        multi_record_event = {
            'Records': [
                {
                    'body': json.dumps({
                        'job_id': 'job_001',
                        'company_client_job': '7central#client1#job_001',
                        'drawing_s3_key': 'path/to/drawing1.pdf',
                        'client_name': 'Client 1',
                        'project_name': 'Project 1',
                        'created_at': 1640995200
                    })
                },
                {
                    'body': json.dumps({
                        'job_id': 'job_002',
                        'company_client_job': '7central#client2#job_002',
                        'drawing_s3_key': 'path/to/drawing2.pdf',
                        'client_name': 'Client 2',
                        'project_name': 'Project 2',
                        'created_at': 1640995200
                    })
                }
            ]
        }
        
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000
        
        mock_storage = AsyncMock()
        mock_storage_manager.get_storage.return_value = mock_storage
        mock_storage.get_file.return_value = mock_pdf_content
        
        with patch('src.lambda_functions.process_drawing_worker.PDFProcessor'), \
             patch('src.lambda.process_drawing_worker.ScheduleAgentV2'), \
             patch('src.lambda.process_drawing_worker.ExcelGenerationAgent'), \
             patch('src.lambda.process_drawing_worker.JudgeAgentV2'):
            
            # Act
            result = handler(multi_record_event, mock_context)
            
            # Assert
            assert result['statusCode'] == 200
            
            response_body = json.loads(result['body'])
            assert response_body['processed_records'] == 2
            assert len(response_body['results']) == 2

    @pytest.mark.asyncio
    async def test_process_job_function_directly(self):
        """Test the process_job function directly for unit-level testing."""
        
        # Arrange
        message_body = {
            'job_id': 'job_test',
            'company_client_job': '7central#test#job_test',
            'drawing_s3_key': 'path/to/test.pdf',
            'context_s3_key': None,
            'client_name': 'Test',
            'project_name': 'Test Project',
            'created_at': 1640995200
        }
        
        mock_storage = AsyncMock()
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000
        
        mock_pdf_content = b'%PDF-1.4\n%test\n%%EOF'
        mock_storage.get_file.return_value = mock_pdf_content
        
        start_time = 1640995200.0
        
        with patch('src.lambda_functions.process_drawing_worker.PDFProcessor') as mock_pdf_processor:
            # Mock minimal success case
            mock_processor_instance = mock_pdf_processor.return_value
            mock_metadata = MagicMock()
            mock_metadata.total_pages = 1
            mock_metadata.pdf_type.value = 'text_based'
            mock_processor_instance.extract_metadata.return_value = mock_metadata
            mock_processor_instance.process_pdf.return_value = ([MagicMock()], None)
            
            with patch('src.lambda_functions.process_drawing_worker.ScheduleAgentV2') as mock_schedule_agent:
                mock_schedule_instance = mock_schedule_agent.return_value
                mock_schedule_instance.process.return_value = {
                    'components': {'pages': [{'components': []}]}
                }
                
                with patch('src.lambda_functions.process_drawing_worker.ExcelGenerationAgent') as mock_excel_agent:
                    mock_excel_instance = mock_excel_agent.return_value
                    mock_excel_instance.process.return_value = {'status': 'completed'}
                    
                    with patch('src.lambda_functions.process_drawing_worker.JudgeAgentV2') as mock_judge_agent:
                        mock_judge_instance = mock_judge_agent.return_value
                        mock_judge_instance.process.return_value = {'evaluation': {}}
                        
                        # Act
                        result = await process_job(mock_storage, message_body, mock_context, start_time)
                        
                        # Assert
                        assert result['status'] == 'completed'
                        assert 'processing_time' in result